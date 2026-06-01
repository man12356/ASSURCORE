# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO01 — OCR Multi-documents AssurCore
#  insurance.document.parser — Orchestrateur OCR 5 types de documents
#
#  Flux complet :
#    Email PDF → alias Odoo → message_new()
#      → _detect_document_type()         ← détecte : contrat/quittance/règlement/avenant/sinistre
#        → _mock_ocr_extract()
#          → _normalize_ocr_data()
#            ├── _create_policy_from_ocr()      → insurance.policy (draft_ocr)
#            ├── _create_receipt_from_ocr()     → insurance.receipt (draft_ocr)
#            ├── _create_settlement_from_ocr()  → insurance.settlement (brouillon)
#            │     └── _generate_bordereau_by_bank()  → insurance.journal.enc (auto)
#            ├── _create_operation_from_ocr()   → insurance.operation (draft)
#            └── _create_claim_from_ocr()       → insurance.claim (declare)
#
#  Phase 1 : bouchon fixe (mock OCR)
#  Phase 2 : appel moteur réel (Google Document AI / Azure Form Recognizer)
# ==============================================================================

import base64
import json
import logging
import re

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

    # ── Types de documents ────────────────────────────────────────────────────
    DOC_TYPE = [
        ('contrat',         'Contrat / Police'),
        ('quittance',       'Quittance / Prime'),
        ('reglement',       'Règlement / Chèque'),
        ('avenant',         'Avenant / Opération'),
        ('sinistre',        'Sinistre / Déclaration'),
        ('piece_identite',  "Pièce d'identité (CIN / MF)"),
        ('autre',           'Autre / Non classifié'),
    ]

    # ── Mots-clés pour la détection automatique du type ──────────────────────
    _DOC_TYPE_KEYWORDS = {
        'sinistre':  ['sinistre', 'accident', 'declaration', 'expertise', 'constat', 'bris', 'incendie'],
        'reglement': ['reglement', 'cheque', 'cheque', 'paiement', 'virement', 'encaissement', 'bordereau'],
        'quittance': ['quittance', 'echeance', 'prime', 'avis', 'appel', 'cotisation'],
        'avenant':   ['avenant', 'modification', 'resiliation', 'suspension', 'remise', 'endossement'],
        'contrat':   ['contrat', 'police', 'souscription', 'attestation'],
    }

    # ── États du parser ───────────────────────────────────────────────────────
    PARSER_STATE = [
        ('pending',    'En attente'),
        ('processing', 'Traitement OCR'),
        ('extracted',  'Données extraites'),
        ('validated',  'Document créé'),
        ('error',      'Erreur'),
    ]

    # ── Champs principaux ─────────────────────────────────────────────────────

    doc_type = fields.Selection(
        selection=DOC_TYPE,
        string='Type de document',
        default='autre',
        required=True,
        tracking=True,
        help='Type détecté automatiquement à partir du sujet/nom du fichier. '
             'Si non reconnu → "autre". L\'utilisateur corrige manuellement, '
             'et le système apprend pour les prochains documents similaires.',
    )

    # ── Liens vers les objets créés (selon doc_type) ──────────────────────────
    receipt_id = fields.Many2one(
        comodel_name='insurance.receipt',
        string='Quittance créée',
        readonly=True, copy=False,
    )
    settlement_id = fields.Many2one(
        comodel_name='insurance.settlement',
        string='Règlement créé',
        readonly=True, copy=False,
    )
    operation_id = fields.Many2one(
        comodel_name='insurance.operation',
        string='Avenant/Opération créé',
        readonly=True, copy=False,
    )
    claim_id = fields.Many2one(
        comodel_name='insurance.claim',
        string='Sinistre créé',
        readonly=True, copy=False,
    )
    bordereau_id = fields.Many2one(
        comodel_name='insurance.journal.enc',
        string='Bordereau généré',
        readonly=True, copy=False,
        help='Bordereau de remise en banque généré automatiquement '
             'si plusieurs règlements en attente pour la même banque.',
    )

    # ── Champs OCR communs (règlement / quittance) ────────────────────────────
    ocr_num_quittance  = fields.Char(string='N° Quittance (OCR)',  readonly=True)
    ocr_montant        = fields.Float(string='Montant TND (OCR)',  digits=(11, 3), readonly=True)
    ocr_date_reg       = fields.Date(string='Date règlement (OCR)', readonly=True)
    ocr_num_cheque     = fields.Char(string='N° Chèque (OCR)',     readonly=True)
    ocr_banque         = fields.Char(string='Banque (OCR)',         readonly=True)
    ocr_type_reg       = fields.Selection(
        selection=[('C', 'Chèque'), ('E', 'Espèces'), ('V', 'Virement')],
        string='Mode règlement (OCR)', readonly=True,
    )
    ocr_type_avenant   = fields.Char(string='Type avenant (OCR)',  readonly=True)
    ocr_type_sinistre  = fields.Char(string='Type sinistre (OCR)', readonly=True)
    ocr_date_sinistre  = fields.Datetime(string='Date sinistre (OCR)', readonly=True)

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

        # Détecter le type de document avant création
        first_filename = ''
        for att in msg_dict.get('attachments', []):
            if isinstance(att, (list, tuple)) and len(att) > 0:
                first_filename = att[0] or ''
            elif isinstance(att, dict):
                first_filename = att.get('name', '')
            if first_filename:
                break

        detected_type = self.with_context()._detect_document_type_static(
            subject, first_filename
        )

        custom_values.update({
            'name':           subject,
            'source_email':   msg_dict.get('email_from', ''),
            'source_subject': subject,
            'state':          'pending',
            'doc_type':       detected_type,
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

        # ── Router vers la méthode de création selon le type de document ──────
        doc_type = self.doc_type or 'autre'

        if doc_type == 'quittance':
            self._create_receipt_from_ocr(normalized, attachment_id)
        elif doc_type == 'reglement':
            self._create_settlement_from_ocr(normalized, attachment_id)
        elif doc_type == 'avenant':
            self._create_operation_from_ocr(normalized, attachment_id)
        elif doc_type == 'sinistre':
            self._create_claim_from_ocr(normalized, attachment_id)
        elif doc_type == 'piece_identite':
            self._create_identity_from_ocr(normalized, attachment_id)
        elif doc_type == 'contrat':
            self._create_policy_from_ocr(normalized, attachment_id)
        else:
            # 'autre' — en attente de classification manuelle
            _logger.info(
                'AssurCore OCR [%s]: doc_type="autre" → en attente classification manuelle',
                self.name,
            )
            self.write({'state': 'pending'})

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

        # ── Recherche intelligente anti-doublon ───────────────────────────────
        # Utilise res.partner._find_partner_smart() qui combine :
        #   CIN exact → MF exact → Nom normalisé → Nom+Ville/Adresse → pg_trgm
        # Retourne (partner, confidence) où confidence ∈ {high, medium, low, None}
        search_vals = {
            'cin':              cin,
            'matricule_fiscal': matricule_fiscal,
            'name':             nom_client,
            'is_company':       company_type == 'company',
        }
        partner, match_confidence = self.env['res.partner']._find_partner_smart(search_vals)

        # Confiance FAIBLE → ne pas accepter automatiquement (laisser au Wizard)
        if match_confidence == 'low':
            _logger.info(
                'AssurCore OCR [%s]: correspondance faible (%.0f%%) pour "%s" '
                '→ validation manuelle requise.',
                self.name, 0, nom_client or 'N/A',
            )
            partner = False

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
        else:
            _logger.info(
                'AssurCore OCR [%s]: client identifié "%s" (id=%d, confiance=%s)',
                self.name, partner.name, partner.id, match_confidence,
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
    #  _detect_document_type — Détection automatique par mots-clés
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _detect_document_type_static(self, subject: str = '', filename: str = '') -> str:
        """
        Détecte le type de document (appelable avant création du record).

        Stratégie :
          1. Consulte insurance.ocr.training (apprentissage pondéré)
          2. Fallback sur mots-clés statiques
          3. Si aucune détection → 'autre' (l'utilisateur corrigera manuellement)
        """
        try:
            doc_type, score = self.env['insurance.ocr.training'].detect_type(
                subject or '', filename or '', ocr_data={}
            )
            if doc_type and doc_type != 'autre' and score >= 2:
                _logger.info(
                    'AssurCore OCR detect_static: "%s" → %s (score=%d) [LEARNED]',
                    (subject or '')[:60], doc_type, score,
                )
                return doc_type
        except Exception as exc:
            _logger.warning('AssurCore OCR: erreur detect_type training — %s', exc)

        # Fallback : mots-clés statiques intégrés
        import unicodedata

        def normalize(s):
            if not s:
                return ''
            nfkd = unicodedata.normalize('NFKD', s.lower())
            return ''.join(c for c in nfkd if not unicodedata.combining(c))

        text = normalize(subject) + ' ' + normalize(filename)
        static_kw = {
            'piece_identite': ['cin', 'cni', 'passeport', 'identite', 'matricule', 'fiscal', 'kbis'],
            'sinistre':  ['sinistre', 'accident', 'declaration', 'expertise', 'constat', 'bris'],
            'reglement': ['reglement', 'cheque', 'paiement', 'virement', 'encaissement'],
            'quittance': ['quittance', 'echeance', 'prime', 'avis', 'appel', 'cotisation'],
            'avenant':   ['avenant', 'modification', 'resiliation', 'suspension'],
            'contrat':   ['contrat', 'police', 'souscription', 'attestation'],
        }
        for doc_type in ['piece_identite', 'sinistre', 'reglement', 'quittance', 'avenant', 'contrat']:
            for kw in static_kw.get(doc_type, []):
                if kw in text:
                    return doc_type

        # Non reconnu → 'autre' pour classification manuelle
        _logger.info(
            'AssurCore OCR detect_static: "%s" → autre (non reconnu)',
            (subject or '')[:60],
        )
        return 'autre'

    def _detect_document_type(self, subject: str = '', filename: str = '') -> str:
        """
        Détecte le type de document à partir du sujet de l'email et/ou du nom
        du fichier PDF en utilisant des mots-clés normalisés (sans accents).

        Priorité de détection : sinistre > règlement > quittance > avenant > contrat

        Returns:
            str : Une valeur parmi DOC_TYPE ('contrat', 'quittance', 'reglement',
                  'avenant', 'sinistre')
        """
        def normalize(s):
            import unicodedata
            if not s:
                return ''
            nfkd = unicodedata.normalize('NFKD', s.lower())
            return ''.join(c for c in nfkd if not unicodedata.combining(c))

        text = normalize(subject) + ' ' + normalize(filename)

        for doc_type in ['sinistre', 'reglement', 'quittance', 'avenant', 'contrat']:
            for kw in self._DOC_TYPE_KEYWORDS.get(doc_type, []):
                if kw in text:
                    _logger.info(
                        'AssurCore OCR [%s]: type détecté = %s (mot-clé: "%s")',
                        self.name, doc_type, kw,
                    )
                    return doc_type

        _logger.info('AssurCore OCR [%s]: type non détecté → défaut "autre"', self.name)
        return 'autre'

    # ─────────────────────────────────────────────────────────────────────────
    #  write — Apprentissage OCR lors de correction manuelle du type
    # ─────────────────────────────────────────────────────────────────────────

    def write(self, vals):
        """
        Surcharge write() pour déclencher l'apprentissage OCR automatique
        quand un utilisateur corrige manuellement le doc_type.

        Règle :
          - Si doc_type change ET que l'ancien type était 'autre'
          - ET que le nouveau type est un type concret (pas 'autre')
          → Extraire les mots-clés du sujet + nom fichier
          → Appeler insurance.ocr.training.learn() avec source='user'
          → Relancer l'extraction OCR avec le bon type
        """
        old_types = {}
        if 'doc_type' in vals:
            for rec in self:
                old_types[rec.id] = rec.doc_type

        result = super().write(vals)

        if 'doc_type' in vals:
            new_type = vals['doc_type']
            if new_type and new_type != 'autre':
                for rec in self:
                    old_type = old_types.get(rec.id)
                    if old_type == 'autre':
                        # Extraire les mots-clés et le contexte métier
                        subject  = rec.source_subject or rec.name or ''
                        filename = rec.attachment_id.name if rec.attachment_id else ''
                        full_text = subject + ' ' + filename

                        # Récupérer les données OCR déjà extraites pour enrichir le contexte
                        ocr_data = {}
                        if rec.normalized_ocr_json:
                            try:
                                import json as _json
                                ocr_data = _json.loads(rec.normalized_ocr_json) or {}
                            except Exception:
                                pass

                        training = self.env['insurance.ocr.training']
                        keywords = training.extract_keywords(full_text)
                        ctx      = training.extract_context(full_text, ocr_data)

                        if keywords:
                            training.learn(
                                keywords, new_type,
                                source='user',
                                parser_id=rec.id,
                                context=ctx,
                            )
                            _logger.info(
                                'AssurCore OCR Learning [%s]: correction "%s" → "%s" '
                                '(%d mots-clés appris)',
                                rec.name, old_type, new_type, len(keywords),
                            )
                        # Relancer l'extraction OCR si un PDF est disponible
                        if rec.attachment_id and rec.state in ('pending', 'error'):
                            try:
                                rec.write({'state': 'processing'})
                                rec._mock_ocr_extract(rec.attachment_id.id)
                            except Exception as exc:
                                rec.write({
                                    'state': 'error',
                                    'error_message': str(exc),
                                })

        return result

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_identity_from_ocr — Pièce d'identité (CIN / MF)
    # ─────────────────────────────────────────────────────────────────────────

    def _create_identity_from_ocr(self, ocr_data: dict, attachment_id: int):
        """
        Traite une pièce d'identité reçue par email (copie CIN ou MF).

        Comportement :
          - Cherche le partenaire correspondant (par nom / CIN / MF)
          - Si trouvé : met à jour son CIN ou son Matricule Fiscal
          - Si non trouvé : crée un partenaire avec les données extraites

        Le PDF source est joint au chatter du partenaire pour traçabilité.
        """
        self.ensure_one()

        nom_client = (ocr_data.get('nom_client') or '').strip()
        cin        = (ocr_data.get('cin') or '').strip()
        mf         = (ocr_data.get('matricule_fiscal') or '').strip()
        is_company = ocr_data.get('company_type') == 'company'

        # ── Recherche du partenaire ───────────────────────────────────────────
        partner, confidence = self.env['res.partner']._find_partner_smart({
            'cin':              cin,
            'matricule_fiscal': mf,
            'name':             nom_client,
            'is_company':       is_company,
        })

        if partner and confidence in ('high', 'medium'):
            update_vals = {}
            # Mise à jour CIN si absent
            if cin and not partner.cin:
                update_vals['cin'] = cin
            # Mise à jour MF si absent
            if mf and not partner.matricule_fiscal:
                update_vals['matricule_fiscal'] = mf
            if update_vals:
                partner.write(update_vals)
                _logger.info(
                    'AssurCore OCR Identity [%s]: partenaire %s mis à jour (%s)',
                    self.name, partner.name, list(update_vals.keys()),
                )
            # Joindre le PDF au chatter du partenaire
            if attachment_id:
                att = self.env['ir.attachment'].browse(attachment_id)
                if att.exists():
                    att.copy({
                        'res_model': 'res.partner',
                        'res_id':    partner.id,
                        'name':      att.name,
                    })
            self.write({
                'state': 'validated',
                'policy_id': False,
            })
            self.message_post(
                body=_(
                    'Pièce d\'identité traitée — Partenaire : <b>%s</b><br/>'
                    'CIN mis à jour : %s | MF mis à jour : %s'
                ) % (partner.name, bool(update_vals.get('cin')), bool(update_vals.get('matricule_fiscal'))),
                subtype_id=self.env.ref('mail.mt_note').id,
            )
        else:
            # Partenaire non trouvé ou faible confiance → créer si données suffisantes
            if nom_client:
                create_vals = {
                    'name':       nom_client,
                    'is_company': is_company,
                }
                if cin:
                    create_vals['cin'] = cin
                if mf:
                    create_vals['matricule_fiscal'] = mf
                new_partner = self.env['res.partner'].create(create_vals)
                if attachment_id:
                    att = self.env['ir.attachment'].browse(attachment_id)
                    if att.exists():
                        att.copy({
                            'res_model': 'res.partner',
                            'res_id':    new_partner.id,
                        })
                self.write({'state': 'validated'})
                _logger.info(
                    'AssurCore OCR Identity [%s]: nouveau partenaire créé "%s"',
                    self.name, nom_client,
                )
            else:
                self.write({
                    'state': 'error',
                    'error_message': 'Pièce identité : aucun nom client extrait par l\'OCR.',
                })

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_receipt_from_ocr — Quittance (insurance.receipt)
    # ─────────────────────────────────────────────────────────────────────────

    def _create_receipt_from_ocr(self, ocr_data: dict, attachment_id: int):
        """
        Crée ou retrouve une quittance (insurance.receipt) en état 'draft_ocr'
        depuis les données OCR normalisées.

        Recherche d'abord par N° quittance + compagnie pour idempotence.
        Utilise _find_partner_smart() pour la résolution du client.
        """
        self.ensure_one()

        # ── Résoudre compagnie ────────────────────────────────────────────────
        company_name = (ocr_data.get('compagnie') or '').strip()
        company = self.env['insurance.company'].search(
            [('name', 'ilike', company_name)], limit=1
        ) if company_name else False
        if not company and company_name:
            company = self.env['insurance.company'].create({'name': company_name})

        # ── Résoudre client (smart match) ─────────────────────────────────────
        partner, confidence = self.env['res.partner']._find_partner_smart({
            'cin':             ocr_data.get('cin', ''),
            'matricule_fiscal': ocr_data.get('matricule_fiscal', ''),
            'name':            ocr_data.get('nom_client', ''),
            'is_company':      ocr_data.get('company_type') == 'company',
        })
        if confidence == 'low':
            partner = False

        # ── Résoudre police ───────────────────────────────────────────────────
        num_police = (ocr_data.get('num_police') or '').strip()
        policy = False
        if num_police and company:
            policy = self.env['insurance.policy'].search([
                ('num_police', '=', num_police),
                ('company_ins_id', '=', company.id),
            ], limit=1)

        # ── Idempotence ───────────────────────────────────────────────────────
        num_quittance = (ocr_data.get('num_quittance') or '').strip()
        existing = False
        if num_quittance and company:
            existing = self.env['insurance.receipt'].search([
                ('name', '=', num_quittance),
            ], limit=1)

        receipt_vals = {
            'partner_id':     partner.id if partner else False,
            'policy_id':      policy.id if policy else False,
            'company_ins_id': company.id if company else False,
            'amount_total':   ocr_data.get('montant', 0.0),
            'date_emission':  ocr_data.get('date_effet') or fields.Date.today().isoformat(),
            'date_echeance':  ocr_data.get('date_echeance') or fields.Date.today().isoformat(),
            'state':          'emise',
            'notes': (
                f'Créée par OCR — {self.source_email or "N/A"}\n'
                f'Confiance client : {confidence or "non trouvé"}'
                + ('' if partner else '\n⚠ Client non identifié — validation manuelle requise.')
            ),
        }

        if existing:
            existing.write(receipt_vals)
            receipt = existing
        else:
            if num_quittance:
                receipt_vals['name'] = num_quittance
            receipt = self.env['insurance.receipt'].create(receipt_vals)

        # ── Lier PDF + màj parser ──────────────────────────────────────────────
        if attachment_id:
            self.env['ir.attachment'].browse(attachment_id).write({
                'res_model': 'insurance.receipt', 'res_id': receipt.id,
            })
            receipt.message_post(
                body=_('Quittance créée par <b>OCR</b> — Source : %s', self.source_email or 'N/A'),
                attachment_ids=[attachment_id],
                subtype_id=self.env.ref('mail.mt_note').id,
            )

        self.write({
            'receipt_id':         receipt.id,
            'state':              'validated',
            'ocr_num_quittance':  num_quittance,
            'ocr_montant':        ocr_data.get('montant', 0.0),
            'ocr_date_effet':     ocr_data.get('date_effet') or False,
        })

        _logger.info('AssurCore OCR [%s]: quittance créée/màj id=%d', self.name, receipt.id)
        return receipt

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_settlement_from_ocr — Règlement + Bordereau automatique
    # ─────────────────────────────────────────────────────────────────────────

    def _create_settlement_from_ocr(self, ocr_data: dict, attachment_id: int):
        """
        Crée un règlement (insurance.settlement) en état 'brouillon' depuis
        les données OCR normalisées.

        Après création, déclenche _generate_bordereau_by_bank() pour regrouper
        automatiquement les règlements OCR en attente par banque.
        """
        self.ensure_one()

        # ── Résoudre client (smart match) ─────────────────────────────────────
        partner, confidence = self.env['res.partner']._find_partner_smart({
            'cin':             ocr_data.get('cin', ''),
            'matricule_fiscal': ocr_data.get('matricule_fiscal', ''),
            'name':            ocr_data.get('nom_client', ''),
            'is_company':      ocr_data.get('company_type') == 'company',
        })
        if confidence == 'low':
            partner = False

        if not partner:
            _logger.warning(
                'AssurCore OCR [%s]: règlement — client "%s" non identifié',
                self.name, ocr_data.get('nom_client', 'N/A'),
            )

        # ── Résoudre banque ───────────────────────────────────────────────────
        banque_nom = (ocr_data.get('banque') or '').strip()
        banque = False
        if banque_nom:
            banque = self.env['insurance.bank'].search(
                ['|', ('name', 'ilike', banque_nom), ('code', 'ilike', banque_nom)], limit=1
            )
            if not banque:
                banque = self.env['insurance.bank'].create({'name': banque_nom})
                _logger.info('AssurCore OCR: banque créée — "%s"', banque_nom)

        # ── Idempotence par N° chèque + banque ───────────────────────────────
        num_cheque = (ocr_data.get('num_cheque') or '').strip()
        existing = False
        if num_cheque and banque:
            existing = self.env['insurance.settlement'].search([
                ('num_cheque', '=', num_cheque),
                ('banque_tireur', '=', banque.id),
            ], limit=1)

        # ── Résoudre quittance liée (si N° fourni) ────────────────────────────
        num_quittance = (ocr_data.get('num_quittance') or '').strip()
        receipt = False
        if num_quittance:
            receipt = self.env['insurance.receipt'].search(
                [('name', '=', num_quittance)], limit=1
            )

        settlement_vals = {
            'partner_id':    partner.id if partner else self.env.ref('base.public_partner').id,
            'receipt_id':    receipt.id if receipt else False,
            'banque_tireur': banque.id if banque else False,
            'num_cheque':    num_cheque,
            'montant_reg':   ocr_data.get('montant', 0.0),
            'type_reg':      ocr_data.get('type_reg', 'C'),
            'date_reg':      ocr_data.get('date_reg') or fields.Date.today().isoformat(),
            'state':         'brouillon',
            'notes': (
                f'Créé par OCR — {self.source_email or "N/A"}\n'
                f'Confiance client : {confidence or "non trouvé"}'
                + ('' if partner else '\n⚠ Client non identifié — validation requise.')
            ),
        }

        if existing:
            existing.write(settlement_vals)
            settlement = existing
        else:
            settlement = self.env['insurance.settlement'].create(settlement_vals)

        # ── Lier PDF + màj parser ──────────────────────────────────────────────
        if attachment_id:
            self.env['ir.attachment'].browse(attachment_id).write({
                'res_model': 'insurance.settlement', 'res_id': settlement.id,
            })
            settlement.message_post(
                body=_('Règlement créé par <b>OCR</b> — Source : %s', self.source_email or 'N/A'),
                attachment_ids=[attachment_id],
                subtype_id=self.env.ref('mail.mt_note').id,
            )

        self.write({
            'settlement_id': settlement.id,
            'state':         'validated',
            'ocr_montant':   ocr_data.get('montant', 0.0),
            'ocr_num_cheque': num_cheque,
            'ocr_banque':    banque_nom,
            'ocr_type_reg':  ocr_data.get('type_reg', 'C'),
            'ocr_date_reg':  ocr_data.get('date_reg') or False,
        })

        # ── Générer bordereau automatique ─────────────────────────────────────
        bordereau = self._generate_bordereau_by_bank(banque, settlement)
        if bordereau:
            self.write({'bordereau_id': bordereau.id})

        _logger.info(
            'AssurCore OCR [%s]: règlement créé id=%d%s',
            self.name, settlement.id,
            f' | bordereau id={bordereau.id}' if bordereau else '',
        )
        return settlement

    # ─────────────────────────────────────────────────────────────────────────
    #  _generate_bordereau_by_bank — Bordereau automatique par banque
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_bordereau_by_bank(self, banque, current_settlement):
        """
        Génère ou met à jour automatiquement un bordereau de remise en banque
        (insurance.journal.enc) en regroupant tous les règlements OCR en attente
        pour la même banque.

        Règle de déclenchement :
          - Au moins 2 règlements en état 'brouillon' pour la même banque tireur
          - OU 1 règlement si un bordereau ouvert existe déjà pour cette banque

        Le bordereau est créé en état 'ouvert' et peut être validé manuellement.

        Args:
            banque             : insurance.bank (peut être False)
            current_settlement : insurance.settlement venant d'être créé

        Returns:
            insurance.journal.enc | False
        """
        self.ensure_one()

        if not banque:
            return False

        # Tous les règlements en brouillon pour cette banque (incluant l'actuel)
        pending = self.env['insurance.settlement'].search([
            ('banque_tireur', '=', banque.id),
            ('state', '=', 'brouillon'),
        ])

        if len(pending) < 2:
            return False  # Pas assez de règlements pour justifier un bordereau

        # Vérifier si un bordereau ouvert existe déjà pour cette banque
        today = fields.Date.today()
        existing_bordereau = self.env['insurance.journal.enc'].search([
            ('banque_enc', 'ilike', banque.name),
            ('state', '=', 'ouvert'),
            ('date_creation', '=', today),
        ], limit=1)

        total = sum(pending.mapped('montant_reg'))
        bordereau_notes = (
            f'Bordereau généré automatiquement par OCR\n'
            f'Banque : {banque.name}\n'
            f'Règlements inclus : {len(pending)}\n'
            f'Total : {total:.3f} TND\n'
            f'Règlements : {", ".join(pending.mapped("name"))}'
        )

        if existing_bordereau:
            existing_bordereau.write({
                'total_montant_enc': total,
                'notes': bordereau_notes,
            })
            _logger.info(
                'AssurCore OCR: bordereau màj id=%d — %d règlements — %.3f TND',
                existing_bordereau.id, len(pending), total,
            )
            # Notifier dans le chatter du bordereau
            existing_bordereau.message_post(
                body=_(
                    'Bordereau mis à jour par OCR — %d règlements ajoutés — Total : %.3f TND',
                    len(pending), total,
                ),
                subtype_id=self.env.ref('mail.mt_note').id,
            )
            return existing_bordereau

        # Créer un nouveau bordereau
        # Déterminer la compagnie depuis le règlement actuel si possible
        company_ins = False
        if current_settlement.receipt_id and current_settlement.receipt_id.company_ins_id:
            company_ins = current_settlement.receipt_id.company_ins_id
        else:
            # Chercher la compagnie la plus fréquente parmi les règlements en attente
            companies = pending.mapped('receipt_id.company_ins_id').filtered(bool)
            if companies:
                company_ins = companies[0]

        if not company_ins:
            # Compagnie inconnue → prendre la première compagnie disponible
            company_ins = self.env['insurance.company'].search([], limit=1)

        if not company_ins:
            _logger.warning('AssurCore OCR: impossible de créer le bordereau — aucune compagnie')
            return False

        bordereau = self.env['insurance.journal.enc'].create({
            'company_ins_id':   company_ins.id,
            'date_creation':    today,
            'banque_enc':       banque.name,
            'type_reg_enc':     'C',
            'total_montant_enc': total,
            'state':            'ouvert',
            'notes':            bordereau_notes,
            'agence_courtier':  self.env.company.name,
        })

        _logger.info(
            'AssurCore OCR: bordereau créé id=%d — banque=%s — %d règlements — %.3f TND',
            bordereau.id, banque.name, len(pending), total,
        )

        bordereau.message_post(
            body=_(
                'Bordereau créé automatiquement par OCR.<br/>'
                '<b>Banque :</b> %s<br/>'
                '<b>Règlements :</b> %d<br/>'
                '<b>Total :</b> %.3f TND',
                banque.name, len(pending), total,
            ),
            subtype_id=self.env.ref('mail.mt_note').id,
        )
        return bordereau

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_operation_from_ocr — Avenant / Opération
    # ─────────────────────────────────────────────────────────────────────────

    def _create_operation_from_ocr(self, ocr_data: dict, attachment_id: int):
        """
        Crée un avenant / opération (insurance.operation) en état 'draft'
        depuis les données OCR.
        """
        self.ensure_one()

        # ── Résoudre police ───────────────────────────────────────────────────
        num_police = (ocr_data.get('num_police') or '').strip()
        company_name = (ocr_data.get('compagnie') or '').strip()
        company = self.env['insurance.company'].search(
            [('name', 'ilike', company_name)], limit=1
        ) if company_name else False

        policy = False
        if num_police:
            domain = [('num_police', '=', num_police)]
            if company:
                domain.append(('company_ins_id', '=', company.id))
            policy = self.env['insurance.policy'].search(domain, limit=1)

        if not policy:
            _logger.warning(
                'AssurCore OCR [%s]: avenant — police "%s" introuvable',
                self.name, num_police or 'N/A',
            )

        # ── Mapper type avenant ───────────────────────────────────────────────
        type_avenant_ocr = (ocr_data.get('type_avenant') or '').upper()
        type_avenant_map = {
            'RESILIATION': 'resiliation',
            'SUSPENSION':  'suspension',
            'MODIF':       'modification',
            'MODIFICATION': 'modification',
            'REMISE':      'remise_en_vigueur',
        }
        type_avenant = 'modification'
        for k, v in type_avenant_map.items():
            if k in type_avenant_ocr:
                type_avenant = v
                break

        operation_vals = {
            'policy_id':    policy.id if policy else False,
            'type_avenant': type_avenant,
            'date_avenant': ocr_data.get('date_effet') or fields.Date.today().isoformat(),
            'state':        'draft',
            'notes': (
                f'Créé par OCR — {self.source_email or "N/A"}\n'
                f'Type OCR : {type_avenant_ocr or "N/A"}'
                + ('' if policy else '\n⚠ Police non identifiée — validation manuelle requise.')
            ),
        }

        operation = self.env['insurance.operation'].create(operation_vals)

        if attachment_id:
            self.env['ir.attachment'].browse(attachment_id).write({
                'res_model': 'insurance.operation', 'res_id': operation.id,
            })
            operation.message_post(
                body=_('Avenant créé par <b>OCR</b> — Source : %s', self.source_email or 'N/A'),
                attachment_ids=[attachment_id],
                subtype_id=self.env.ref('mail.mt_note').id,
            )

        self.write({
            'operation_id':   operation.id,
            'state':          'validated',
            'ocr_type_avenant': type_avenant_ocr,
        })

        _logger.info('AssurCore OCR [%s]: avenant créé id=%d', self.name, operation.id)
        return operation

    # ─────────────────────────────────────────────────────────────────────────
    #  _create_claim_from_ocr — Sinistre (insurance.claim)
    # ─────────────────────────────────────────────────────────────────────────

    def _create_claim_from_ocr(self, ocr_data: dict, attachment_id: int):
        """
        Crée un sinistre (insurance.claim) en état 'declare' depuis les données OCR.
        Utilise _find_partner_smart() pour la résolution du client.
        """
        self.ensure_one()

        # ── Résoudre police ───────────────────────────────────────────────────
        num_police = (ocr_data.get('num_police') or '').strip()
        company_name = (ocr_data.get('compagnie') or '').strip()
        company = self.env['insurance.company'].search(
            [('name', 'ilike', company_name)], limit=1
        ) if company_name else False

        policy = False
        if num_police:
            domain = [('num_police', '=', num_police)]
            if company:
                domain.append(('company_ins_id', '=', company.id))
            policy = self.env['insurance.policy'].search(domain, limit=1)

        # ── Résoudre client (smart match) ─────────────────────────────────────
        partner, confidence = self.env['res.partner']._find_partner_smart({
            'cin':             ocr_data.get('cin', ''),
            'matricule_fiscal': ocr_data.get('matricule_fiscal', ''),
            'name':            ocr_data.get('nom_client', ''),
            'is_company':      ocr_data.get('company_type') == 'company',
        })
        if confidence == 'low':
            partner = False

        # Préférer le client de la police si trouvé
        if not partner and policy and policy.partner_id:
            partner = policy.partner_id

        # ── Mapper type sinistre ──────────────────────────────────────────────
        type_sin_ocr = (ocr_data.get('type_sinistre') or '').upper()
        type_sin_map = {
            'AUTO': 'AUTO', 'ACCIDENT': 'AUTO', 'COLLISION': 'AUTO',
            'INCENDIE': 'INCENDIE', 'FIRE': 'INCENDIE',
            'VOL': 'VOL', 'THEFT': 'VOL',
            'BRIS': 'BRIS_GLACE', 'GLACE': 'BRIS_GLACE',
            'MEDICAL': 'MEDICAL', 'SANTE': 'MEDICAL',
            'RC': 'RC',
        }
        type_sinistre = 'AUTRE'
        for k, v in type_sin_map.items():
            if k in type_sin_ocr:
                type_sinistre = v
                break

        from datetime import datetime
        date_sin_str = ocr_data.get('date_sinistre')
        date_sinistre = False
        if date_sin_str:
            try:
                date_sinistre = datetime.fromisoformat(date_sin_str)
            except Exception:
                date_sinistre = datetime.now()
        else:
            date_sinistre = datetime.now()

        claim_vals = {
            'policy_id':     policy.id if policy else False,
            'date_sinistre': date_sinistre,
            'type_sinistre': type_sinistre,
            'state':         'declare',
            'description': (
                f'Sinistre déclaré via OCR — {self.source_email or "N/A"}\n'
                f'Type OCR : {type_sin_ocr or "N/A"}\n'
                f'Confiance client : {confidence or "non trouvé"}'
                + ('' if partner else '\n⚠ Client non identifié — validation requise.')
                + ('' if policy else '\n⚠ Police non identifiée — validation requise.')
            ),
        }

        claim = self.env['insurance.claim'].create(claim_vals)

        if attachment_id:
            self.env['ir.attachment'].browse(attachment_id).write({
                'res_model': 'insurance.claim', 'res_id': claim.id,
            })
            claim.message_post(
                body=_('Sinistre déclaré par <b>OCR</b> — Source : %s', self.source_email or 'N/A'),
                attachment_ids=[attachment_id],
                subtype_id=self.env.ref('mail.mt_note').id,
            )

        self.write({
            'claim_id':         claim.id,
            'state':            'validated',
            'ocr_type_sinistre': type_sin_ocr,
            'ocr_date_sinistre': date_sinistre,
        })

        _logger.info('AssurCore OCR [%s]: sinistre créé id=%d', self.name, claim.id)
        return claim

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
