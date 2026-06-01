# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.ocr.training -- Apprentissage automatique OCR AssurCore
#
#  Principe :
#    Chaque fois qu'un utilisateur corrige manuellement le type d'un document
#    non reconnu (type='autre'), le systeme extrait les mots-cles significatifs
#    du sujet email et du nom de fichier, et les stocke avec le type correct.
#
#    Lors de la prochaine detection, la table d'apprentissage est consultee
#    EN PRIORITE avant les mots-cles statiques. Plus un mot-cle a ete confirme,
#    plus sa confiance est haute (hit_count).
#
#  Contexte metier (optionnel mais tres puissant) :
#    Chaque regle d'apprentissage peut etre affinees par :
#      - Compagnie d'assurance  (ex: MAGHREBIA, STAR, GAT, COMAR...)
#      - Banque tireur/payeur   (ex: STB, BNA, BIAT, ATB...)
#      - Marque vehicule        (ex: PEUGEOT, RENAULT, VOLKSWAGEN...)
#      - Branche assurance      (ex: Auto, Vie, IARD, Sante...)
#      - Type operation         (ex: Nouvelle souscription, Renouvellement...)
#
#    Un mot-cle sans contexte = regle generale (s'applique partout).
#    Un mot-cle AVEC contexte = regle specialisee (score booste x3 si contexte
#    correspond, ignoree si contexte contradictoire).
#
#  Cycle de vie :
#    Email non reconnu -> type='autre' (manuel)
#      -> utilisateur affecte le bon type
#        -> learn() extrait les mots-cles + contexte detecte
#          -> insurance.ocr.training crees/mis a jour (hit_count++)
#            -> prochain email similaire -> detecte automatiquement
#
#  Cas particulier 'piece_identite' :
#    Copie CIN -> mise a jour res.partner.cin
#    Copie MF  -> mise a jour res.partner.matricule_fiscal
# ==============================================================================

import unicodedata
import re
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# -- Mots vides a ignorer lors de l'extraction de mots-cles -------------------
_STOP_WORDS = {
    'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'ou', 'en',
    'sur', 'par', 'pour', 'avec', 'sans', 'dans', 'ce', 'se', 'sa', 'son',
    'mon', 'ton', 'notre', 'votre', 'the', 'a', 'an', 'of', 'to', 'in',
    'pdf', 'doc', 'scan', 'image', 'img', 'file', 'fwd', 're', 'fw',
    'copie', 'copy', 'original', 'num', 'ref', 'numero',
}

# -- Marques automobiles connues en Tunisie -----------------------------------
_VEHICLE_BRANDS = [
    'peugeot', 'renault', 'volkswagen', 'ford', 'toyota', 'hyundai', 'kia',
    'fiat', 'citroen', 'bmw', 'mercedes', 'audi', 'opel', 'seat', 'skoda',
    'nissan', 'honda', 'mazda', 'suzuki', 'mitsubishi', 'chevrolet', 'jeep',
    'dacia', 'lada', 'land', 'rover', 'volvo', 'mini', 'alfa',
]

# -- Branches assurance standard ----------------------------------------------
_BRANCHES = [
    ('auto',           'Automobile'),
    ('vie',            'Vie / Prevoyance'),
    ('iard',           'IARD (Incendie / Accidents / RC)'),
    ('sante',          'Sante / Maladie'),
    ('transport',      'Transport / Maritime'),
    ('agricole',       'Agricole'),
    ('responsabilite', 'Responsabilite Civile'),
    ('autre_branche',  'Autre branche'),
]

# -- Types d'operation --------------------------------------------------------
_OPERATION_TYPES = [
    ('souscription',       'Nouvelle souscription'),
    ('renouvellement',     'Renouvellement'),
    ('resiliation',        'Resiliation'),
    ('suspension',         'Suspension'),
    ('modification',       'Modification'),
    ('remise_en_vigueur',  'Remise en vigueur'),
]


class InsuranceOcrTraining(models.Model):
    """
    Table d'apprentissage OCR -- Association mot-cle -> type de document.

    Le contexte metier (compagnie, banque, marque, branche, type operation)
    est OPTIONNEL mais permet une detection beaucoup plus precise.

    Regle de scoring lors de la detection :
      - Correspondance keyword seul         -> score = hit_count x 1 (ou x2 si user)
      - Correspondance keyword + compagnie  -> score x 3
      - Correspondance keyword + banque     -> score x 3
      - Correspondance keyword + marque     -> score x 2
      - Correspondance keyword + branche    -> score x 2
    """

    _name        = 'insurance.ocr.training'
    _description = 'Apprentissage OCR - Mots-cles / Contexte / Types de documents'
    _order       = 'hit_count desc, keyword'
    _rec_name    = 'keyword'

    # -- Mot-cle --------------------------------------------------------------

    keyword = fields.Char(
        string='Mot-cle',
        required=True,
        index=True,
        help='Mot-cle normalise extrait du sujet email ou du nom de fichier PDF.',
    )

    doc_type = fields.Selection(
        selection=[
            ('contrat',         'Contrat / Police'),
            ('quittance',       'Quittance / Prime'),
            ('reglement',       'Reglement / Cheque'),
            ('avenant',         'Avenant / Operation'),
            ('sinistre',        'Sinistre / Declaration'),
            ('piece_identite',  "Piece d'identite (CIN / MF)"),
            ('autre',           'Autre / Non classifie'),
        ],
        string='Type de document',
        required=True,
        index=True,
    )

    # -- Contexte metier (optionnel) ------------------------------------------

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string="Compagnie d'assurance",
        ondelete='set null',
        index=True,
        help='Si renseignee, cette regle ne s\'applique qu\'aux documents '
             'de cette compagnie (MAGHREBIA, STAR, GAT, COMAR, LLOYD...). '
             'Laissez vide pour une regle generale toutes compagnies.',
    )

    bank_id = fields.Many2one(
        comodel_name='insurance.bank',
        string='Banque',
        ondelete='set null',
        index=True,
        help='Si renseignee, cette regle ne s\'applique qu\'aux documents '
             'lies a cette banque (STB, BNA, BIAT, ATB, Zitouna...). '
             'Particulierement utile pour les reglements et bordereaux.',
    )

    vehicle_brand = fields.Char(
        string='Marque vehicule',
        size=50,
        index=True,
        help='Marque automobile normalisee (PEUGEOT, RENAULT, VOLKSWAGEN...). '
             'Permet de distinguer les formats de documents par concessionnaire.',
    )

    insurance_branch = fields.Selection(
        selection=_BRANCHES,
        string='Branche assurance',
        index=True,
        help='Branche d\'assurance concernee : Auto, Vie, IARD, Sante, Transport...',
    )

    operation_type = fields.Selection(
        selection=_OPERATION_TYPES,
        string="Type d'operation",
        help='Type d\'operation specifique appris. '
             'Ex: "RESIL" -> resiliation ; "RENOUV" -> renouvellement.',
    )

    # -- Statistiques de confiance --------------------------------------------

    hit_count = fields.Integer(
        string='Confirmations',
        default=1,
        help='Nombre de fois que ce mot-cle + contexte a ete confirme. '
             'Plus ce compteur est eleve, plus la detection est prioritaire.',
    )

    source = fields.Selection(
        selection=[
            ('user',   'Correction utilisateur'),
            ('auto',   'Detection automatique confirmee'),
            ('system', 'Regle systeme initiale'),
        ],
        string='Source',
        default='user',
        required=True,
        help='"user" = correction manuelle (poids x2 dans le score).',
    )

    last_used = fields.Datetime(
        string='Derniere utilisation',
        default=fields.Datetime.now,
    )

    parser_id = fields.Many2one(
        comodel_name='insurance.document.parser',
        string='Document source',
        ondelete='set null',
    )

    # -- Champ calcule : resume du contexte -----------------------------------

    context_summary = fields.Char(
        string='Contexte',
        compute='_compute_context_summary',
        store=False,
    )

    @api.depends('company_ins_id', 'bank_id', 'vehicle_brand',
                 'insurance_branch', 'operation_type')
    def _compute_context_summary(self):
        branch_labels = dict(_BRANCHES)
        op_labels     = dict(_OPERATION_TYPES)
        for rec in self:
            parts = []
            if rec.company_ins_id:
                parts.append(rec.company_ins_id.name)
            if rec.bank_id:
                parts.append(rec.bank_id.name)
            if rec.vehicle_brand:
                parts.append(rec.vehicle_brand.upper())
            if rec.insurance_branch:
                parts.append(branch_labels.get(rec.insurance_branch, ''))
            if rec.operation_type:
                parts.append(op_labels.get(rec.operation_type, ''))
            rec.context_summary = ' / '.join(filter(None, parts)) or u'—'

    # -- Contrainte unicite : keyword + doc_type + contexte ------------------
    # Un meme mot-cle peut exister plusieurs fois avec des contextes differents.

    _sql_constraints = [
        (
            'keyword_doctype_context_uniq',
            'UNIQUE(keyword, doc_type, company_ins_id, bank_id, vehicle_brand, insurance_branch)',
            'Ce mot-cle est deja enregistre pour ce type et ce contexte.',
        ),
    ]

    # =========================================================================
    #  Methodes utilitaires
    # =========================================================================

    @api.model
    def normalize_keyword(self, word):
        """Normalise un mot : minuscules, sans accents, sans ponctuation."""
        if not word:
            return ''
        nfkd  = unicodedata.normalize('NFKD', word.lower())
        clean = ''.join(c for c in nfkd if not unicodedata.combining(c))
        clean = re.sub(r'[^\w]', '', clean)
        return clean

    @api.model
    def extract_keywords(self, text):
        """Extrait les mots-cles significatifs d'un texte (sujet email ou nom fichier)."""
        if not text:
            return []
        words    = re.split(r'[\s\-_\.\,\/\\]+', text.lower())
        keywords = []
        for w in words:
            kw = self.normalize_keyword(w)
            if len(kw) >= 3 and kw not in _STOP_WORDS and kw not in keywords:
                keywords.append(kw)
        return keywords

    @api.model
    def extract_context(self, text, ocr_data=None):
        """
        Extrait le contexte metier depuis un texte et/ou des donnees OCR.

        Detecte : compagnie, banque, marque vehicule, branche, type operation.
        Retourne un dict avec les cles trouvees uniquement.
        """
        ocr_data  = ocr_data or {}
        context   = {}
        text_norm = self.normalize_keyword(text or '')

        # -- Compagnie d'assurance --------------------------------------------
        company_name = (ocr_data.get('compagnie') or '').strip()
        if company_name:
            company = self.env['insurance.company'].search(
                [('name', 'ilike', company_name)], limit=1
            )
            if company:
                context['company_ins_id'] = company.id
        if 'company_ins_id' not in context:
            for comp in self.env['insurance.company'].search([]):
                norm = self.normalize_keyword(comp.name)
                if norm and norm in text_norm:
                    context['company_ins_id'] = comp.id
                    break

        # -- Banque -----------------------------------------------------------
        bank_name = (ocr_data.get('banque') or '').strip()
        if bank_name:
            bank = self.env['insurance.bank'].search(
                [('name', 'ilike', bank_name)], limit=1
            )
            if bank:
                context['bank_id'] = bank.id
        if 'bank_id' not in context:
            for bank in self.env['insurance.bank'].search([]):
                norm = self.normalize_keyword(bank.name)
                if norm and norm in text_norm:
                    context['bank_id'] = bank.id
                    break

        # -- Marque vehicule --------------------------------------------------
        brand_ocr = (
            ocr_data.get('marque_vehicule') or
            ocr_data.get('vehicle_brand') or ''
        ).strip().lower()
        if brand_ocr:
            context['vehicle_brand'] = brand_ocr.upper()
        else:
            for brand in _VEHICLE_BRANDS:
                if brand in text_norm:
                    context['vehicle_brand'] = brand.upper()
                    break

        # -- Branche assurance ------------------------------------------------
        branch_map = {
            'auto':           ['auto', 'vehicule', 'voiture', 'automobile', 'immat'],
            'vie':            ['vie', 'deces', 'prevoyance', 'invalidite', 'retraite'],
            'iard':           ['iard', 'incendie', 'responsabilite', 'habitation', 'multirisque'],
            'sante':          ['sante', 'maladie', 'hospitalisation', 'medical', 'frais'],
            'transport':      ['transport', 'maritime', 'fret', 'cargaison'],
            'agricole':       ['agricole', 'recolte', 'betail', 'serres'],
            'responsabilite': ['rc', 'responsabilite', 'civile', 'decennale'],
        }
        for branch_code, branch_kws in branch_map.items():
            if any(kw in text_norm for kw in branch_kws):
                context['insurance_branch'] = branch_code
                break

        # -- Type d'operation -------------------------------------------------
        op_map = {
            'souscription':      ['souscription', 'nouveau', 'nouvelle', 'ouverture'],
            'renouvellement':    ['renouvellement', 'renouv', 'reconduction', 'echeance'],
            'resiliation':       ['resiliation', 'resil', 'annulation', 'terme'],
            'suspension':        ['suspension', 'suspendu', 'suspen'],
            'modification':      ['modification', 'modif', 'avenant', 'endossement'],
            'remise_en_vigueur': ['remise', 'vigueur', 'regularisation', 'reprise'],
        }
        for op_code, op_kws in op_map.items():
            if any(kw in text_norm for kw in op_kws):
                context['operation_type'] = op_code
                break

        return context

    @api.model
    def learn(self, keywords, doc_type, source='user',
              parser_id=None, context=None):
        """
        Enregistre ou renforce les associations mot-cle -> type + contexte metier.

        Strategie de stockage :
          - Toujours creer la regle generale (sans contexte) pour la portabilite.
          - Si un contexte est detecte, creer AUSSI la regle specialisee
            (score booste x3 lors de la detection si contexte correspond).
        """
        context = context or {}
        for kw in keywords:
            # Regle generale (sans contexte)
            self._learn_one(kw, doc_type, source, parser_id, {})
            # Regle specialisee (avec contexte si disponible)
            ctx_vals = {
                k: v for k, v in context.items()
                if k in ('company_ins_id', 'bank_id', 'vehicle_brand',
                         'insurance_branch', 'operation_type')
                and v
            }
            if ctx_vals:
                self._learn_one(kw, doc_type, source, parser_id, ctx_vals)

    @api.model
    def _learn_one(self, kw, doc_type, source, parser_id, context_vals):
        """Cree ou incremente un seul enregistrement d'apprentissage."""
        domain = [
            ('keyword',          '=', kw),
            ('doc_type',         '=', doc_type),
            ('company_ins_id',   '=', context_vals.get('company_ins_id', False)),
            ('bank_id',          '=', context_vals.get('bank_id', False)),
            ('vehicle_brand',    '=', context_vals.get('vehicle_brand', False)),
            ('insurance_branch', '=', context_vals.get('insurance_branch', False)),
        ]
        existing = self.search(domain, limit=1)
        if existing:
            existing.write({
                'hit_count': existing.hit_count + 1,
                'last_used': fields.Datetime.now(),
                'source':    source if source == 'user' else existing.source,
            })
            _logger.debug(
                'OCR Learning: "%s" -> %s [ctx:%s] (hits=%d)',
                kw, doc_type,
                ','.join(str(v) for v in context_vals.values()),
                existing.hit_count + 1,
            )
        else:
            vals = {
                'keyword':   kw,
                'doc_type':  doc_type,
                'hit_count': 1,
                'source':    source,
                'last_used': fields.Datetime.now(),
            }
            vals.update(context_vals)
            if parser_id:
                vals['parser_id'] = parser_id
            self.create(vals)
            _logger.debug(
                'OCR Learning: nouveau "%s" -> %s [ctx:%s]',
                kw, doc_type,
                ','.join(str(v) for v in context_vals.values()),
            )

    @api.model
    def detect_type(self, subject, filename, ocr_data=None):
        """
        Detecte le type de document en combinant :
          1. Table d'apprentissage avec contexte metier (score pondere)
          2. Mots-cles statiques (fallback)

        Regle de scoring SQL :
          - Base        : hit_count x (2 si source='user', sinon 1)
          - Bonus compagnie  : multiplicateur x3
          - Bonus banque     : multiplicateur x3
          - Bonus marque     : multiplicateur x2
          - Bonus branche    : multiplicateur x2

        Returns:
            tuple (doc_type, confidence_score)
        """
        ocr_data  = ocr_data or {}
        full_text = (subject or '') + ' ' + (filename or '')
        keywords  = self.extract_keywords(full_text)
        if not keywords:
            return 'autre', 0

        ctx        = self.extract_context(full_text, ocr_data)
        company_id = ctx.get('company_ins_id') or 0
        bank_id    = ctx.get('bank_id') or 0
        brand      = ctx.get('vehicle_brand') or ''
        branch     = ctx.get('insurance_branch') or ''

        # -- 1. Consulter la table d'apprentissage avec bonus contexte --------
        try:
            self.env.cr.execute("""
                SELECT
                    doc_type,
                    SUM(
                        hit_count
                        * CASE WHEN source = 'user' THEN 2 ELSE 1 END
                        * CASE
                            WHEN company_ins_id IS NOT NULL
                             AND company_ins_id = %(company_id)s THEN 3
                            WHEN bank_id IS NOT NULL
                             AND bank_id = %(bank_id)s           THEN 3
                            WHEN vehicle_brand IS NOT NULL
                             AND vehicle_brand = %(brand)s       THEN 2
                            WHEN insurance_branch IS NOT NULL
                             AND insurance_branch = %(branch)s   THEN 2
                            WHEN company_ins_id IS NULL
                             AND bank_id IS NULL
                             AND vehicle_brand IS NULL
                             AND insurance_branch IS NULL         THEN 1
                            ELSE 0
                          END
                    ) AS score
                FROM insurance_ocr_training
                WHERE keyword = ANY(%(kws)s)
                  AND doc_type != 'autre'
                  AND (
                    (company_ins_id IS NULL AND bank_id IS NULL
                     AND vehicle_brand IS NULL AND insurance_branch IS NULL)
                    OR (%(company_id)s > 0 AND company_ins_id = %(company_id)s)
                    OR (%(bank_id)s    > 0 AND bank_id = %(bank_id)s)
                    OR (%(brand)s != '' AND vehicle_brand = %(brand)s)
                    OR (%(branch)s != '' AND insurance_branch = %(branch)s)
                  )
                GROUP BY doc_type
                HAVING SUM(
                    hit_count
                    * CASE WHEN source = 'user' THEN 2 ELSE 1 END
                    * CASE
                        WHEN company_ins_id IS NOT NULL
                         AND company_ins_id = %(company_id)s THEN 3
                        WHEN bank_id IS NOT NULL
                         AND bank_id = %(bank_id)s           THEN 3
                        WHEN vehicle_brand IS NOT NULL
                         AND vehicle_brand = %(brand)s       THEN 2
                        WHEN insurance_branch IS NOT NULL
                         AND insurance_branch = %(branch)s   THEN 2
                        ELSE 1
                      END
                ) >= 2
                ORDER BY score DESC
                LIMIT 1
            """, {
                'kws':        keywords,
                'company_id': company_id,
                'bank_id':    bank_id,
                'brand':      brand,
                'branch':     branch,
            })
            row = self.env.cr.fetchone()
            if row and row[1] and row[1] >= 2:
                _logger.info(
                    'OCR detect [LEARNED]: "%s" -> %s (score=%d, cmp=%s bk=%s brand=%s br=%s)',
                    (subject or '')[:50], row[0], row[1],
                    company_id or '-', bank_id or '-',
                    brand or '-', branch or '-',
                )
                return row[0], int(row[1])

        except Exception as exc:
            _logger.warning('OCR detect_type SQL error: %s', exc)

        # -- 2. Mots-cles statiques (fallback) --------------------------------
        static_keywords = {
            'piece_identite': ['cin', 'cni', 'passeport', 'identite', 'matricule', 'fiscal', 'kbis'],
            'sinistre':       ['sinistre', 'accident', 'declaration', 'expertise', 'constat', 'bris', 'incendie'],
            'reglement':      ['reglement', 'cheque', 'paiement', 'virement', 'encaissement', 'bordereau'],
            'quittance':      ['quittance', 'echeance', 'prime', 'avis', 'appel', 'cotisation'],
            'avenant':        ['avenant', 'modification', 'resiliation', 'suspension', 'endossement'],
            'contrat':        ['contrat', 'police', 'souscription', 'attestation'],
        }

        text_norm = self.normalize_keyword(full_text)
        for dtype in ['piece_identite', 'sinistre', 'reglement',
                      'quittance', 'avenant', 'contrat']:
            for kw in static_keywords.get(dtype, []):
                if kw in text_norm:
                    _logger.info(
                        'OCR detect [STATIC]: "%s" -> %s (mot-cle: "%s")',
                        (subject or '')[:50], dtype, kw,
                    )
                    self.learn([kw], dtype, source='auto', context=ctx)
                    return dtype, 1

        return 'autre', 0
