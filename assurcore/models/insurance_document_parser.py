# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO01 — Étape 1 : Réception Email & Mock OCR
#  insurance.document.parser + extension insurance.policy (état draft_ocr)
#
#  Flux complet :
#    Email PDF → alias Odoo → message_new()
#      → _mock_ocr_extract(attachment_id)
#        → _normalize_ocr_data(raw_data, company_code)
#          → _create_policy_from_ocr(normalized, attachment_id)
#            → insurance.policy(state='draft_ocr') + PDF dans le Chatter
#
#  Phase 1 (ce fichier) : bouchon fixe — données ABIDI ANOUAR / MAGHREBIA
#  Phase 2 (future)     : appel à un vrai moteur OCR (Google Document AI,
#                         Azure Form Recognizer, PaddleOCR…) dans
#                         _mock_ocr_extract() qui deviendra _ocr_extract()
# ==============================================================================

import base64
import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  Extension insurance.policy — Ajout du statut 'draft_ocr'
#
#  Utilise selection_add (Odoo 17) pour ne pas écraser la sélection d'origine.
#  ondelete={'draft_ocr': 'set default'} : si ce module est désinstallé,
#  les polices en draft_ocr repassent à 'draft'.
# ─────────────────────────────────────────────────────────────────────────────

class InsurancePolicyOCRState(models.Model):
    """
    Extension de insurance.policy pour ajouter le statut 'draft_ocr'
    et le lien vers le parser OCR source.
    """

    _inherit = 'insurance.policy'

    state = fields.Selection(
        selection_add=[('draft_ocr', 'Brouillon OCR (à valider)')],
        ondelete={'draft_ocr': 'set default'},
    )

    document_parser_id = fields.Many2one(
        comodel_name='insurance.document.parser',
        string='Document OCR source',
        readonly=True,
        ondelete='set null',
        help='Parser OCR qui a généré ce brouillon de police. '
             'Cliquer pour voir le document PDF original et les données extraites.',
    )

    # ── Champs temporaires OCR (EVO01 Étape 2) ───────────────────────────────
    # Stockent les données brutes quand le client n'a PAS été trouvé
    # automatiquement. Vidés par le Wizard de validation (insurance.ocr.wizard)
    # une fois que l'opérateur a confirmé ou créé le bon partenaire.

    ocr_raw_partner_name = fields.Char(
        string='Nom client brut (OCR)',
        copy=False,
        help='Nom du client tel que lu par l\'OCR, conservé si aucun '
             'res.partner correspondant n\'a été trouvé automatiquement. '
             'L\'opérateur utilise ce champ dans le Wizard de validation '
             'pour rechercher ou créer manuellement le bon client.',
    )

    ocr_raw_cin = fields.Char(
        string='CIN brut (OCR)',
        copy=False,
        help='CIN lu par l\'OCR, conservé si aucun res.partner '
             'correspondant n\'a été trouvé automatiquement.',
    )

    # ── Champs B2B — Entreprises (EVO01 Étape 2.5) ────────────────────────────
    # Gèrent le cas où l'assuré est une société (Matricule Fiscal / RC)
    # plutôt qu'une personne physique (CIN).

    ocr_raw_company_type = fields.Selection(
        selection=[('person', 'Personne physique'), ('company', 'Entreprise')],
        string='Type assuré (OCR)',
        copy=False,
        help='Type d\'entité lu par l\'OCR. '
             '"person" → recherche par CIN ; "company" → recherche par Matricule Fiscal.',
    )

    ocr_raw_matricule_fiscal = fields.Char(
        string='Matricule Fiscal brut (OCR)',
        copy=False,
        help='Matricule Fiscal tunisien lu par l\'OCR, conservé si aucune '
             'entreprise correspondante n\'a été trouvée automatiquement.',
    )

    def action_open_ocr_wizard(self):
        """Ouvre le Wizard de validation OCR depuis la fiche police."""
        self.ensure_one()
        return {
            'type':    'ir.actions.act_window',
            'name':    'Valider le brouillon OCR',
            'res_model': 'insurance.ocr.wizard',
            'view_mode': 'form',
            'target':  'new',
            'context': {'default_policy_id': self.id},
        }

    def action_validate_ocr_draft(self):
        """
        Transition manuelle : Brouillon OCR → Brouillon classique.
        L'opérateur a vérifié les données extraites et valide la police.
        """
        for rec in self:
            if rec.state == 'draft_ocr':
                rec.write({'state': 'draft'})
                rec.message_post(
                    body=_('Police validée manuellement depuis le brouillon OCR.'),
                    subtype_id=self.env.ref('mail.mt_note').id,
                )

    def action_test_ocr(self):
        """
        Simule la réception et le parsing OCR d'un document.
        Crée un document.parser factice avec une pièce jointe vide,
        puis appelle _mock_ocr_extract() pour générer/mettre à jour la police.
        """
        import base64
        self.ensure_one()

        ctx = {
            'mock_policy_num': self.num_police,
            'mock_company_name': self.company_ins_id.name,
            'mock_client_name': 'Foulen Ben Foulen',
            'mock_cin': '01234567',
            'mock_company_type': 'person',
            'mock_prime_totale': self.prime_nette,
        }

        # Crée un parser de test
        parser = self.env['insurance.document.parser'].with_context(ctx).create({
            'name': 'Simulation manuelle ' + (self.num_police or ''),
            'source_email': self.env.user.email or 'admin@example.com',
            'source_subject': 'Simulation OCR',
        })
        # Crée un attachment factice
        attachment = self.env['ir.attachment'].create({
            'name': 'simulation.pdf',
            'datas': base64.b64encode(b'mock_pdf_content').decode('ascii'),
            'res_model': 'insurance.document.parser',
            'res_id': parser.id,
            'mimetype': 'application/pdf',
        })
        parser.write({
            'attachment_id': attachment.id,
            'state': 'processing',
        })
        # Lance l'extraction sur ce parser
        parser.with_context(ctx)._mock_ocr_extract(attachment.id)
        # Rafraîchit l'affichage
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


# ─────────────────────────────────────────────────────────────────────────────
#  insurance.document.parser — Orchestrateur OCR
# ─────────────────────────────────────────────────────────────────────────────

class InsuranceDocumentParser(models.Model):
    """
    Modèle central du workflow d'importation OCR de documents assurance.

    Fonctionnement :
      1. Un utilisateur (ou un script) envoie un email avec un PDF en PJ
         à l'alias Odoo configuré sur ce modèle.
      2. message_new() est déclenché par le serveur mail d'Odoo.
      3. Le PDF est sauvegardé en ir.attachment.
      4. _mock_ocr_extract() simule l'extraction (Phase 1 = bouchon fixe).
      5. _normalize_ocr_data() standardise les données au format AssurCore.
      6. _create_policy_from_ocr() crée la police en état 'draft_ocr'
         avec le PDF joint dans son Chatter.

    Configuration de l'alias :
      Odoo → Paramètres → Serveurs de messagerie entrants
      → Créer un alias pointant sur insurance.document.parser
    """

    _name        = 'insurance.document.parser'
    _description = 'Parseur de Documents Assurance (OCR)'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'create_date desc'
    _rec_name    = 'name'

    # ── États du parser ───────────────────────────────────────────────────────
    PARSER_STATE = [
        ('pending',    'En attente'),
        ('processing', 'Traitement OCR'),
        ('extracted',  'Données extraites'),
        ('validated',  'Police créée'),
        ('error',      'Erreur'),
    ]

    # ── Champs principaux ─────────────────────────────────────────────────────

    name = fields.Char(
        string='Référence',
        required=True,
        copy=False,
        default=lambda self: _('Nouveau document'),
        tracking=True,
    )

    state = fields.Selection(
        selection=PARSER_STATE,
        string='État',
        default='pending',
        required=True,
        tracking=True,
    )

    # ── Source email ──────────────────────────────────────────────────────────

    source_email = fields.Char(
        string='Expéditeur',
        readonly=True,
        help='Adresse email de l\'expéditeur du document.',
    )

    source_subject = fields.Char(
        string='Sujet email',
        readonly=True,
    )

    # ── Pièce jointe PDF ──────────────────────────────────────────────────────

    attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='PDF source',
        readonly=True,
        help='Pièce jointe PDF originale reçue par email.',
    )

    # ── Données OCR (stockées en JSON pour auditabilité complète) ─────────────

    raw_ocr_json = fields.Text(
        string='Données OCR brutes (JSON)',
        readonly=True,
        help='Sortie brute du moteur OCR avant normalisation. '
             'Utile pour le débogage et l\'audit.',
    )

    normalized_ocr_json = fields.Text(
        string='Données normalisées (JSON)',
        readonly=True,
        help='Dictionnaire standardisé AssurCore après normalisation.',
    )

    # ── Champs extraits (lisibles dans l'interface) ────────────────────────────

    ocr_compagnie      = fields.Char(string='Compagnie (OCR)',      readonly=True)
    ocr_num_police     = fields.Char(string='N° Police (OCR)',       readonly=True)
    ocr_nom_client     = fields.Char(string='Assuré (OCR)',          readonly=True)
    ocr_cin            = fields.Char(string='CIN (OCR)',             readonly=True)
    ocr_immatriculation = fields.Char(string='Immatriculation (OCR)', readonly=True)
    ocr_prime_totale   = fields.Float(
        string='Prime totale TND (OCR)',
        digits=(11, 3),
        readonly=True,
    )
    ocr_date_effet     = fields.Date(string='Date effet (OCR)',      readonly=True)
    ocr_date_echeance  = fields.Date(string='Date échéance (OCR)',   readonly=True)

    # ── Police générée ────────────────────────────────────────────────────────

    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police créée',
        readonly=True,
        copy=False,
    )

    error_message = fields.Text(string='Message d\'erreur', readonly=True)

    # ─────────────────────────────────────────────────────────────────────────
    #  message_new — Point d'entrée email (surcharge mail.thread)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        Intercepte les emails entrants sur l'alias Odoo de ce modèle.

        Comportement :
          - Crée l'enregistrement insurance.document.parser via super()
          - Détecte les pièces jointes PDF dans msg_dict['attachments']
          - Sauvegarde le premier PDF trouvé en ir.attachment
          - Déclenche _mock_ocr_extract() sur cet attachment

        Args:
            msg_dict      (dict) : Données de l'email (subject, from, attachments…)
            custom_values (dict) : Valeurs override pour la création
        """
        custom_values = custom_values or {}
        subject = (msg_dict.get('subject') or 'Document sans sujet')[:128]

        custom_values.update({
            'name':           subject,
            'source_email':   msg_dict.get('email_from', ''),
            'source_subject': subject,
            'state':          'pending',
        })

        # Créer le record (mail.thread gère le message initial)
        parser = super().message_new(msg_dict, custom_values)

        # ── Détecter et sauvegarder le premier PDF ───────────────────────────
        pdf_attachment_id = None

        for attachment in msg_dict.get('attachments', []):

            # Normaliser le format de l'attachment
            # Odoo peut fournir un tuple (name, content, mimetype, ...)
            # ou un dict selon la version
            if isinstance(attachment, (list, tuple)):
                att_name     = attachment[0] if len(attachment) > 0 else 'document.pdf'
                att_content  = attachment[1] if len(attachment) > 1 else b''
                att_mimetype = attachment[2] if len(attachment) > 2 else 'application/octet-stream'
            elif isinstance(attachment, dict):
                att_name     = attachment.get('name', 'document.pdf')
                att_content  = attachment.get('content', b'')
                att_mimetype = attachment.get('mimetype', 'application/octet-stream')
            else:
                continue

            # Filtrer sur les PDF uniquement
            is_pdf = (
                att_mimetype == 'application/pdf'
                or (isinstance(att_name, str) and att_name.lower().endswith('.pdf'))
            )

            if not is_pdf or not att_content:
                continue

            # Encoder en base64 pour ir.attachment
            if isinstance(att_content, bytes):
                datas_b64 = base64.b64encode(att_content).decode('ascii')
            else:
                datas_b64 = base64.b64encode(
                    att_content.encode('latin-1', errors='replace')
                ).decode('ascii')

            try:
                attach = self.env['ir.attachment'].create({
                    'name':      att_name,
                    'datas':     datas_b64,
                    'res_model': self._name,
                    'res_id':    parser.id,
                    'mimetype':  'application/pdf',
                })
                pdf_attachment_id = attach.id
                _logger.info(
                    'AssurCore OCR [%s]: PDF sauvegardé — "%s" (attachment.id=%d)',
                    parser.name, att_name, attach.id,
                )
                break  # On traite uniquement le premier PDF reçu

            except Exception as exc:
                _logger.error(
                    'AssurCore OCR [%s]: impossible de sauvegarder "%s" — %s',
                    parser.name, att_name, exc,
                )

        # ── Déclencher l'extraction OCR ───────────────────────────────────────
        if pdf_attachment_id:
            parser.write({'state': 'processing'})
            try:
                parser._mock_ocr_extract(pdf_attachment_id)
            except Exception as exc:
                _logger.error(
                    'AssurCore OCR [%s]: erreur extraction — %s', parser.name, exc
                )
                parser.write({
                    'state':         'error',
                    'error_message': str(exc),
                })
        else:
            _logger.warning(
                'AssurCore OCR: email "%s" reçu sans PDF — parser ID=%d',
                subject, parser.id,
            )

        return parser

    # ─────────────────────────────────────────────────────────────────────────
    #  _mock_ocr_extract — Bouchon du moteur OCR (Phase 1)
    # ─────────────────────────────────────────────────────────────────────────

    def _mock_ocr_extract(self, attachment_id: int) -> dict:
        """
        Bouchon (Mock) du moteur OCR — Phase 1.

        Simule la réponse d'un vrai moteur OCR en retournant un dictionnaire
        fixe correspondant à des données réelles du portefeuille AssurCore.
        Les données retournées dépendent du nom de la pièce jointe pour faciliter
        les tests réels avec différents types de contrats.

        Args:
            attachment_id (int) : ID de l'ir.attachment PDF source

        Returns:
            dict : Dictionnaire normalisé AssurCore
        """
        self.ensure_one()

        attachment = self.env['ir.attachment'].browse(attachment_id)
        filename = attachment.name or ''
        filename_upper = filename.upper()

        # Valeurs par défaut (cas MAGHREBIA / B2C)
        compagnie = 'MAGHREBIA'
        num_police = 'J54554'
        nom_assure = 'ABIDI ANOUAR'
        cin = '08422621'
        immat = 'RS294328'
        prime = '2858.781'
        date_debut = '15/05/2026'
        date_fin = '14/05/2027'
        company_type = 'person'
        matricule_fiscal = ''

        # Mocks personnalisés basés sur le nom du fichier PDF pour test réel
        if 'LLOYD' in filename_upper:
            compagnie = 'LLOYD ASSURANCES'
            num_police = 'POL-LLOYD-7788'
            nom_assure = 'BEN ALI SLIM'
            cin = '09876543'
            immat = '110 TU 9876'
            prime = '1200.500'
            date_debut = '01/06/2026'
            date_fin = '31/05/2027'
        elif 'CARTE' in filename_upper:
            compagnie = 'CARTE ASSURANCES'
            num_police = 'POL-CARTE-5544'
            nom_assure = 'GHARBI SELIMA'
            cin = '07654321'
            immat = '220 TU 4321'
            prime = '850.350'
            date_debut = '15/07/2026'
            date_fin = '14/07/2027'
        elif 'SCAN' in filename_upper or 'contrat_assistance' in filename:
            # Cas B2B (Entreprise)
            compagnie = 'STAR'
            num_police = 'POL-STAR-B2B-100'
            nom_assure = 'SOCIETE TUNISIENNE DE BOIS'
            company_type = 'company'
            matricule_fiscal = '1234567/A/B/M/000'
            immat = '190 TU 5566'
            prime = '5400.000'
            date_debut = '01/08/2026'
            date_fin = '31/07/2027'
        elif 'J54554' in filename_upper or 'contrat J54554' in filename:
            compagnie = 'MAGHREBIA'
            num_police = 'J54554'
            nom_assure = 'ABIDI ANOUAR'
            cin = '08422621'
            immat = 'RS294328'
            prime = '2858.781'
            date_debut = '15/05/2026'
            date_fin = '14/05/2027'

        raw_data = {
            'source':          'mock_ocr_v1',
            'attachment_id':   attachment_id,
            'confidence':      0.95,
            'pages_analyzed':  1,
            'engine':          'MockOCR/1.0 — Phase 2: remplacer par moteur réel',
            'raw_fields': {
                'COMPAGNIE':      compagnie,
                'POLICE_NUM':     num_police,
                'NOM_ASSURE':     nom_assure,
                'CIN_ASSURE':     cin,
                'IMMAT_VEHICULE': immat,
                'PRIME_TTC':      prime,
                'DATE_DEBUT':     date_debut,
                'DATE_FIN':       date_fin,
                'COMPANY_TYPE':   company_type,
                'MATRICULE_FISCAL': matricule_fiscal,
            },
        }

        # Persister les données brutes pour auditabilité
        self.write({
            'raw_ocr_json': json.dumps(raw_data, ensure_ascii=False, indent=2),
        })

        # Appel au normalisateur
        company_code = raw_data['raw_fields'].get('COMPAGNIE', 'INCONNU')
        normalized   = self._normalize_ocr_data(raw_data, company_code)

        # Génération du brouillon de police
        self._create_policy_from_ocr(normalized, attachment_id)

        return normalized

    # ─────────────────────────────────────────────────────────────────────────
    #  _normalize_ocr_data — Normalisateur multi-compagnies
    # ─────────────────────────────────────────────────────────────────────────

    def _normalize_ocr_data(self, raw_data: dict, company_code: str) -> dict:
        """
        Normalise les données brutes OCR en un dictionnaire standard AssurCore.

        Chaque compagnie (MAGHREBIA, STAR, GAT, COMAR…) peut nommer ses champs
        différemment sur ses documents. Ce normalisateur applique les règles de
        mapping spécifiques à chaque compagnie pour produire un dictionnaire
        uniforme consommable par _create_policy_from_ocr().

        Convention du dictionnaire de sortie (immuable) :
          compagnie       (str)   : Nom normalisé de la compagnie
          num_police      (str)   : Numéro de police exact
          nom_client      (str)   : Nom complet de l'assuré
          cin             (str)   : CIN tunisien (8 chiffres)
          immatriculation (str)   : Numéro de plaque tunisien
          prime_totale    (float) : Prime TTC en TND (3 décimales)
          date_effet      (str)   : Début couverture ISO 8601 (YYYY-MM-DD)
          date_echeance   (str)   : Fin couverture ISO 8601 (YYYY-MM-DD)

        Args:
            raw_data     (dict) : Sortie brute du moteur OCR
            company_code (str)  : Code compagnie pour adapter la logique

        Returns:
            dict : Données standardisées AssurCore (dictionnaire fixe Phase 1)
        """
        self.ensure_one()

        # ── Phase 2 : décommenter et implémenter le routing par compagnie ─────
        # company_upper = company_code.upper()
        # if 'MAGHREBIA' in company_upper:
        #     normalized = self._normalize_maghrebia(raw_data)
        # elif 'STAR' in company_upper:
        #     normalized = self._normalize_star(raw_data)
        # elif 'GAT' in company_upper:
        #     normalized = self._normalize_gat(raw_data)
        # else:
        #     normalized = self._normalize_generic(raw_data)

        # ── Phase 1 : dictionnaire fixe (données réelles AssurCore) ──────────
        #
        # CONVENTION DU DICTIONNAIRE NORMALISÉ (immuable entre phases) :
        #   company_type      (str)   : 'person' | 'company'
        #   compagnie         (str)   : Nom de la compagnie d'assurance
        #   num_police        (str)   : Numéro de police
        #   nom_client        (str)   : Nom / Raison sociale de l'assuré
        #   cin               (str)   : CIN 8 chiffres (si company_type='person')
        #   matricule_fiscal  (str)   : MF tunisien  (si company_type='company')
        #   immatriculation   (str)   : Plaque véhicule (si branche Auto)
        #   prime_totale      (float) : Prime TTC en TND
        #   date_effet        (str)   : ISO 8601 YYYY-MM-DD
        #   date_echeance     (str)   : ISO 8601 YYYY-MM-DD
        #
        # Exemple B2C (personne physique) — utilisé comme mock actuel :
        #   {'company_type': 'person', 'cin': '08422621', ...}
        #
        # Exemple B2B (entreprise) — décommenter pour tester :
        #   {'company_type': 'company',
        #    'nom_client': 'SOCIETE TUNISIENNE DE TRANSPORT',
        #    'matricule_fiscal': '1234567/A/B/M/000', ...}

        def parse_date_to_iso(date_str):
            if date_str and '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    return f"{parts[2]}-{parts[1]}-{parts[0]}"
            return date_str

        raw_fields = raw_data.get('raw_fields', {})

        normalized = {
            'company_type':    self.env.context['mock_company_type'] if 'mock_company_type' in self.env.context else raw_fields.get('COMPANY_TYPE', 'person'),
            'compagnie':       self.env.context['mock_company_name'] if 'mock_company_name' in self.env.context else raw_fields.get('COMPAGNIE', 'MAGHREBIA'),
            'num_police':      self.env.context['mock_policy_num'] if 'mock_policy_num' in self.env.context else raw_fields.get('POLICE_NUM', 'J54554'),
            'nom_client':      self.env.context['mock_client_name'] if 'mock_client_name' in self.env.context else raw_fields.get('NOM_ASSURE', 'ABIDI ANOUAR'),
            'cin':             self.env.context['mock_cin'] if 'mock_cin' in self.env.context else raw_fields.get('CIN_ASSURE', '08422621'),
            'matricule_fiscal': self.env.context['mock_matricule_fiscal'] if 'mock_matricule_fiscal' in self.env.context else raw_fields.get('MATRICULE_FISCAL', ''),
            'immatriculation': self.env.context['mock_immatriculation'] if 'mock_immatriculation' in self.env.context else raw_fields.get('IMMAT_VEHICULE', 'RS294328'),
            'prime_totale':    float(self.env.context['mock_prime_totale'] if 'mock_prime_totale' in self.env.context else raw_fields.get('PRIME_TTC', 2858.781)),
            'date_effet':      self.env.context['mock_date_effet'] if 'mock_date_effet' in self.env.context else parse_date_to_iso(raw_fields.get('DATE_DEBUT', '15/05/2026')),
            'date_echeance':   self.env.context['mock_date_echeance'] if 'mock_date_echeance' in self.env.context else parse_date_to_iso(raw_fields.get('DATE_FIN', '14/05/2027')),
        }

        # Persister les données normalisées
        self.write({
            'normalized_ocr_json': json.dumps(
                normalized, ensure_ascii=False, indent=2
            ),
            'state': 'extracted',
        })

        _logger.info(
            'AssurCore OCR [%s]: normalisation terminée — %s / %s',
            self.name,
            normalized.get('compagnie'),
            normalized.get('num_police'),
        )

        return normalized

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_policy_from_ocr — Génération du brouillon insurance.policy
    # ─────────────────────────────────────────────────────────────────────────

    def _create_policy_from_ocr(
        self, ocr_data: dict, attachment_id: int
    ) -> 'models.Model':
        """
        Crée ou met à jour un enregistrement insurance.policy en état 'draft_ocr'
        à partir du dictionnaire normalisé.

        Mapping OCR → ORM Odoo :
          ocr_data['compagnie']       → insurance.company (recherche/création)
          ocr_data['nom_client']      → res.partner        (recherche via CIN / nom)
          ocr_data['num_police']      → insurance.policy.num_police
          ocr_data['cin']             → res.partner.cin
          ocr_data['immatriculation'] → insurance.policy.matricule
          ocr_data['prime_totale']    → insurance.policy.prime_nette
          ocr_data['date_effet']      → insurance.policy.date_effect
          ocr_data['date_echeance']   → insurance.policy.date_echeance

        Le PDF source est automatiquement lié au Chatter de la police créée.

        Args:
            ocr_data      (dict) : Dictionnaire normalisé
            attachment_id (int)  : ID de l'ir.attachment PDF source

        Returns:
            insurance.policy : La police brouillon créée ou mise à jour
        """
        self.ensure_one()

        # ── 1. Résoudre la compagnie d'assurance ──────────────────────────────
        company_name = ocr_data.get('compagnie', '').strip()
        company      = self.env['insurance.company'].search(
            [('name', 'ilike', company_name)], limit=1
        )
        if not company and company_name:
            company = self.env['insurance.company'].create({'name': company_name})
            _logger.info('AssurCore OCR: compagnie créée — "%s"', company_name)

        # ── 2. Résoudre le client (JAMAIS créer automatiquement — EVO01 Étape 2) ─
        #
        # RÈGLE MÉTIER : Le script automatique ne crée JAMAIS un res.partner
        # de son propre chef pour éviter les doublons. Si aucun client n'est
        # trouvé, la police est créée en draft_ocr avec les champs ocr_raw_*
        # renseignés. L'opérateur humain valide via insurance.ocr.wizard.
        #
        # Stratégie de recherche (EVO01 Étape 2.5 — B2B/B2C) :
        #   company_type='person'  → priorité CIN, repli nom exact
        #   company_type='company' → priorité Matricule Fiscal, repli raison sociale
        nom_client       = ocr_data.get('nom_client', '').strip()
        cin              = ocr_data.get('cin', '').strip()
        company_type     = ocr_data.get('company_type', 'person')   # 'person' | 'company'
        matricule_fiscal = ocr_data.get('matricule_fiscal', '').strip()

        partner = False

        if company_type == 'company':
            # ── B2B : Entreprise ─────────────────────────────────────────────
            # 1. Recherche par Matricule Fiscal (identifiant unique entreprise TN)
            if matricule_fiscal:
                partner = self.env['res.partner'].search([
                    ('matricule_fiscal', '=', matricule_fiscal),
                    ('is_company', '=', True),
                ], limit=1)
            # 2. Repli par Raison Sociale exacte (parmi les sociétés seulement)
            if not partner and nom_client:
                partner = self.env['res.partner'].search([
                    ('name', '=', nom_client),
                    ('is_company', '=', True),
                ], limit=1)
        else:
            # ── B2C : Personne physique ───────────────────────────────────────
            # 1. Recherche prioritaire par CIN (identifiant unique en Tunisie)
            if cin:
                partner = self.env['res.partner'].search([
                    ('cin', '=', cin),
                ], limit=1)
            # 2. Repli par nom exact (ilike trop permissif pour la production)
            if not partner and nom_client:
                partner = self.env['res.partner'].search([
                    ('name', '=', nom_client),
                ], limit=1)

        # Client NON trouvé → stocker les données brutes pour le Wizard
        if not partner:
            _logger.warning(
                'AssurCore OCR [%s]: %s "%s" (%s: %s) introuvable — '
                'wizard de validation requis.',
                self.name,
                'Entreprise' if company_type == 'company' else 'Client',
                nom_client or 'N/A',
                'MF' if company_type == 'company' else 'CIN',
                matricule_fiscal or cin or 'N/A',
            )

        # ── 3. Idempotence : police déjà importée ? ───────────────────────────
        num_police = ocr_data.get('num_police', '').strip()
        existing   = False
        if num_police and company:
            existing = self.env['insurance.policy'].search([
                ('num_police',     '=',  num_police),
                ('company_ins_id', '=',  company.id),
            ], limit=1)

        # ── 4. Construire les valeurs communes ────────────────────────────────
        date_effect   = ocr_data.get('date_effet')   or fields.Date.today().isoformat()
        date_echeance = ocr_data.get('date_echeance') or fields.Date.today().isoformat()

        policy_vals = {
            'state':               'draft_ocr',
            'num_police':          num_police,
            'company_ins_id':      company.id if company else False,
            # partner_id : renseigné si trouvé, sinon vide → Wizard
            'partner_id':          partner.id if partner else False,
            'payer_id':            partner.id if partner else False,
            'raison_sociale':      nom_client,
            'branche':             'AUTO',   # Déduit : immatriculation présente → Auto
            'matricule':           ocr_data.get('immatriculation', ''),
            'prime_nette':         ocr_data.get('prime_totale', 0.0),
            'date_effect':         date_effect,
            'date_echeance':       date_echeance,
            'document_parser_id':  self.id,
            # Champs temporaires (EVO01 Étape 2) : remplis si client non trouvé
            'ocr_raw_partner_name': nom_client if not partner else False,
            'ocr_raw_cin':          cin        if not partner else False,
            'ocr_raw_company_type': company_type if not partner else False,
            'ocr_raw_matricule_fiscal': matricule_fiscal if not partner else False,
            'notes': (
                f'Brouillon créé automatiquement par OCR.\n'
                f'Parser : {self.name} | Source : {self.source_email or "N/A"}\n'
                f'Compagnie OCR : {ocr_data.get("compagnie")} | '
                f'N° Police OCR : {num_police}'
                + (f'\n⚠ Client non trouvé — validation manuelle requise.'
                   if not partner else '')
            ),
        }

        # ── 5. Créer ou mettre à jour ─────────────────────────────────────────
        if existing:
            existing.write(policy_vals)
            policy = existing
            _logger.info(
                'AssurCore OCR: police mise à jour — %s (id=%d)',
                num_police, policy.id,
            )
        else:
            policy = self.env['insurance.policy'].create(policy_vals)
            _logger.info(
                'AssurCore OCR: police brouillon créée — %s (id=%d)',
                num_police, policy.id,
            )

        # ── 6. Lier le PDF au Chatter de la police ────────────────────────────
        if attachment_id:
            attachment = self.env['ir.attachment'].browse(attachment_id)
            if attachment.exists():
                # Réattacher le PDF à la police (pas au parser)
                attachment.write({
                    'res_model': 'insurance.policy',
                    'res_id':    policy.id,
                })

                # Message dans le Chatter avec PDF joint
                policy.message_post(
                    body=_(
                        'Police créée automatiquement par <b>OCR</b>.<br/>'
                        '<b>Source :</b> %(subject)s '
                        '(<i>%(sender)s</i>)<br/>'
                        '<b>Données extraites :</b> '
                        '%(compagnie)s — Police <b>%(num_police)s</b> — '
                        'Assuré <b>%(client)s</b><br/>'
                        'Prime TTC : <b>%(prime).3f TND</b>',
                        subject=self.source_subject or '(sans sujet)',
                        sender=self.source_email or 'N/A',
                        compagnie=ocr_data.get('compagnie', '?'),
                        num_police=num_police or '?',
                        client=nom_client or '?',
                        prime=ocr_data.get('prime_totale', 0.0),
                    ),
                    attachment_ids=[attachment_id],
                    subtype_id=self.env.ref('mail.mt_note').id,
                )

        # ── 7. Finaliser le parser ────────────────────────────────────────────
        self.write({
            'state':               'validated',
            'attachment_id':       attachment_id,
            'policy_id':           policy.id,
            'ocr_compagnie':       ocr_data.get('compagnie', ''),
            'ocr_num_police':      ocr_data.get('num_police', ''),
            'ocr_nom_client':      ocr_data.get('nom_client', ''),
            'ocr_cin':             ocr_data.get('cin', ''),
            'ocr_immatriculation': ocr_data.get('immatriculation', ''),
            'ocr_prime_totale':    ocr_data.get('prime_totale', 0.0),
            'ocr_date_effet':      ocr_data.get('date_effet')    or False,
            'ocr_date_echeance':   ocr_data.get('date_echeance') or False,
        })

        return policy

    # ─────────────────────────────────────────────────────────────────────────
    #  Action manuelle (test hors email)
    # ─────────────────────────────────────────────────────────────────────────

    def action_test_ocr(self):
        """
        Déclenche l'extraction OCR manuellement depuis l'interface Odoo.
        Utile pour tester sans avoir à envoyer un vrai email.
        Recherche en priorité un PDF joint dans le Chatter si aucun attachment_id.
        """
        self.ensure_one()
        if not self.attachment_id:
            # Recherche d'un PDF dans les pièces jointes associées (Chatter)
            attachment = self.env['ir.attachment'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('mimetype', '=', 'application/pdf'),
            ], limit=1)
            if attachment:
                self.attachment_id = attachment.id
            else:
                return {
                    'type':    'ir.actions.client',
                    'tag':     'display_notification',
                    'params':  {
                        'title':   _('Aucun PDF'),
                        'message': _('Veuillez d\'abord ajouter un fichier PDF dans les pièces jointes (Chatter).'),
                        'type':    'warning',
                    },
                }

        self.write({'state': 'processing'})
        try:
            self._mock_ocr_extract(self.attachment_id.id)
        except Exception as exc:
            self.write({'state': 'error', 'error_message': str(exc)})
            raise

        return {
            'type':   'ir.actions.client',
            'tag':    'display_notification',
            'params': {
                'title':   _('OCR terminé'),
                'message': _(
                    'Police %(num)s créée en brouillon OCR.',
                    num=self.ocr_num_police or '?',
                ),
                'type':    'success',
                'next':    {'type': 'ir.actions.act_window_close'},
            },
        }
