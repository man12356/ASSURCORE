# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.ocr.classify.wizard — Assistant de Classification OCR (2 etapes)
#
#  Flux :
#    Document recu type='autre' (non reconnu par l'OCR)
#      → Bouton "Classifier ce document" → wizard s'ouvre
#
#  Etape 1 — IDENTIFICATION
#    Affiche : apercu PDF + donnees brutes OCR + suggestion du systeme
#    L'operateur selectionne le type : contrat / quittance / reglement /
#    avenant / sinistre / piece_identite / autre
#    → Bouton "Suivant"
#
#  Etape 2 — PARAMETRES
#    Affiche les champs specifiques au type selectionne,
#    pre-remplis depuis les donnees OCR si disponibles :
#      Contrat        : compagnie, client, police, prime, dates
#      Quittance      : compagnie, client, police, montant, dates
#      Reglement      : compagnie, client, banque, cheque, montant, date
#      Avenant        : compagnie, client, police, type avenant
#      Sinistre       : compagnie, client, police, type sinistre, date
#      Piece identite : nom, cin, matricule fiscal, type (physique/moral)
#    → Bouton "Valider et creer la piece"
#
#  Confirmation :
#    Cree la piece Odoo (police / quittance / reglement / avenant / sinistre)
#    Declenche l'apprentissage OCR (learn() avec source='user' + contexte)
#    Ferme le wizard
# ==============================================================================

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class InsuranceOcrClassifyWizard(models.TransientModel):
    """
    Assistant de classification manuelle des documents OCR non reconnus.

    Wizard en 2 etapes (champ 'wizard_step' controle l'affichage XML) :
      'identify' → operateur choisit le type de document
      'params'   → operateur confirme/complete les parametres (pre-remplis OCR)
    """

    _name        = 'insurance.ocr.classify.wizard'
    _description = 'Assistant Classification Document OCR (2 etapes)'

    # ── Etat du wizard ────────────────────────────────────────────────────────

    wizard_step = fields.Selection(
        selection=[
            ('identify', 'Etape 1 — Identification du type'),
            ('params',   'Etape 2 — Parametres et validation'),
        ],
        string='Etape',
        default='identify',
        required=True,
    )

    # ── Lien vers le parser source ────────────────────────────────────────────

    parser_id = fields.Many2one(
        comodel_name='insurance.document.parser',
        string='Document OCR source',
        required=True,
        ondelete='cascade',
    )

    # ── Donnees brutes du parser (affichage lecture seule etape 1) ────────────

    parser_subject   = fields.Char(related='parser_id.source_subject', readonly=True, string='Sujet email')
    parser_email     = fields.Char(related='parser_id.source_email',   readonly=True, string='Expediteur')
    parser_file      = fields.Many2one(related='parser_id.attachment_id', readonly=True, string='Fichier PDF')
    ocr_suggestion   = fields.Char(
        string='Suggestion OCR',
        compute='_compute_ocr_suggestion',
        help='Type propose par l\'OCR avant la correction manuelle.',
    )

    @api.depends('parser_id')
    def _compute_ocr_suggestion(self):
        type_labels = {
            'contrat':        'Contrat / Police',
            'quittance':      'Quittance / Prime',
            'reglement':      'Reglement / Cheque',
            'avenant':        'Avenant / Operation',
            'sinistre':       'Sinistre / Declaration',
            'piece_identite': "Piece d'identite (CIN / MF)",
            'autre':          'Non reconnu',
        }
        for rec in self:
            if rec.parser_id:
                t = rec.parser_id.doc_type or 'autre'
                rec.ocr_suggestion = type_labels.get(t, t)
            else:
                rec.ocr_suggestion = ''

    # ── Etape 1 : selection du type ───────────────────────────────────────────

    doc_type = fields.Selection(
        selection=[
            ('contrat',         'Contrat / Police'),
            ('quittance',       'Quittance / Prime'),
            ('reglement',       'Reglement / Cheque'),
            ('avenant',         'Avenant / Operation'),
            ('sinistre',        'Sinistre / Declaration'),
            ('piece_identite',  "Piece d'identite (CIN / MF)"),
            ('autre',           'Autre (non classifiable)'),
        ],
        string='Type de document',
        required=True,
        default='contrat',
        help='Selectionnez le type de document. '
             'L\'OCR apprendra de cette correction pour les prochains envois.',
    )

    # ── Etape 2 : parametres communs ──────────────────────────────────────────

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        help='Compagnie d\'assurance concernee.',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client / Assure',
        domain=[('customer_rank', '>', 0)],
        options="{'no_create': True}",
    )
    create_new_partner = fields.Boolean(
        string='Creer un nouveau client',
        default=False,
    )
    new_partner_name = fields.Char(string='Nom du nouveau client')
    new_partner_cin  = fields.Char(string='CIN',              size=8)
    new_partner_mf   = fields.Char(string='Matricule Fiscal', size=20)
    new_partner_type = fields.Selection(
        selection=[('person', 'Personne physique'), ('company', 'Entreprise')],
        string='Type',
        default='person',
    )

    # ── Etape 2 : police ──────────────────────────────────────────────────────

    num_police = fields.Char(
        string='N° Police',
        help='Numero de police associee a ce document.',
    )
    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police existante',
        help='Si la police existe deja dans Odoo, selectionnez-la ici.',
    )

    # ── Etape 2 : montants / dates ────────────────────────────────────────────

    montant = fields.Float(string='Montant TND', digits=(11, 3))
    date_doc = fields.Date(string='Date du document', default=fields.Date.today)
    date_echeance = fields.Date(string='Date echeance')
    date_effet    = fields.Date(string='Date effet')

    # ── Etape 2 : reglement specifique ────────────────────────────────────────

    bank_id = fields.Many2one(
        comodel_name='insurance.bank',
        string='Banque tireur',
    )
    num_cheque = fields.Char(string='N° Cheque', size=30)
    type_reg   = fields.Selection(
        selection=[('C', 'Cheque'), ('E', 'Especes'), ('V', 'Virement')],
        string='Mode reglement',
        default='C',
    )

    # ── Etape 2 : avenant specifique ─────────────────────────────────────────

    type_avenant = fields.Selection(
        selection=[
            ('modification',       'Modification'),
            ('resiliation',        'Resiliation'),
            ('suspension',         'Suspension'),
            ('remise_en_vigueur',  'Remise en vigueur'),
            ('renouvellement',     'Renouvellement'),
            ('autre',              'Autre'),
        ],
        string='Type avenant',
        default='modification',
    )

    # ── Etape 2 : sinistre specifique ────────────────────────────────────────

    type_sinistre = fields.Selection(
        selection=[
            ('accident',   'Accident de la route'),
            ('incendie',   'Incendie'),
            ('vol',        'Vol'),
            ('bris_glace', 'Bris de glace'),
            ('catastrophe','Catastrophe naturelle'),
            ('rc',         'Responsabilite civile'),
            ('autre',      'Autre'),
        ],
        string='Type sinistre',
        default='accident',
    )
    date_sinistre = fields.Datetime(string='Date et heure du sinistre')

    # ── Etape 2 : piece identite specifique ──────────────────────────────────

    identity_nom = fields.Char(string='Nom complet')
    identity_cin = fields.Char(string='CIN', size=8)
    identity_mf  = fields.Char(string='Matricule Fiscal')
    identity_type = fields.Selection(
        selection=[('cin', 'CIN (personne physique)'), ('mf', "Matricule Fiscal (entreprise)")],
        string='Type piece identite',
        default='cin',
    )

    # ── Donnees OCR pre-remplies ──────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        """
        Pre-remplit les champs de l'etape 2 depuis les donnees OCR
        du parser source (si disponibles).
        """
        res = super().default_get(fields_list)
        parser_id = (
            self.env.context.get('default_parser_id') or
            self.env.context.get('active_id')
        )
        if not parser_id:
            return res

        parser = self.env['insurance.document.parser'].browse(parser_id)
        if not parser.exists():
            return res

        # Recuperer les donnees OCR normalisees
        ocr = {}
        if parser.normalized_ocr_json:
            try:
                ocr = json.loads(parser.normalized_ocr_json) or {}
            except Exception:
                pass

        # Pre-remplir compagnie
        company_name = (ocr.get('compagnie') or parser.ocr_compagnie or '').strip()
        if company_name:
            company = self.env['insurance.company'].search(
                [('name', 'ilike', company_name)], limit=1
            )
            if company:
                res['company_ins_id'] = company.id

        # Pre-remplir client (si trouve)
        if parser.policy_id and parser.policy_id.partner_id:
            res['partner_id'] = parser.policy_id.partner_id.id

        # Pre-remplir police
        res['num_police']  = ocr.get('num_police')  or parser.ocr_num_police  or ''
        res['montant']     = ocr.get('montant')      or parser.ocr_montant     or 0.0
        res['num_cheque']  = ocr.get('num_cheque')   or parser.ocr_num_cheque  or ''

        # Pre-remplir banque
        banque_name = (ocr.get('banque') or parser.ocr_banque or '').strip()
        if banque_name:
            bank = self.env['insurance.bank'].search(
                [('name', 'ilike', banque_name)], limit=1
            )
            if bank:
                res['bank_id'] = bank.id

        # Pre-remplir dates
        if ocr.get('date_effet') or parser.ocr_date_effet:
            res['date_effet'] = ocr.get('date_effet') or parser.ocr_date_effet
        if ocr.get('date_echeance') or parser.ocr_date_echeance:
            res['date_echeance'] = ocr.get('date_echeance') or parser.ocr_date_echeance
        if ocr.get('date_reg') or parser.ocr_date_reg:
            res['date_doc'] = ocr.get('date_reg') or parser.ocr_date_reg

        # Pre-remplir piece identite
        res['identity_nom'] = ocr.get('nom_client') or parser.ocr_nom_client or ''
        res['identity_cin'] = ocr.get('cin')        or parser.ocr_cin        or ''
        res['identity_mf']  = ocr.get('matricule_fiscal', '')

        # Pre-remplir champs nom pour nouveau client
        res['new_partner_name'] = ocr.get('nom_client') or parser.ocr_nom_client or ''
        res['new_partner_cin']  = ocr.get('cin')        or parser.ocr_cin        or ''
        res['new_partner_mf']   = ocr.get('matricule_fiscal', '')

        return res

    # ── Navigation wizard ─────────────────────────────────────────────────────

    def action_next_step(self):
        """
        Etape 1 → Etape 2.
        Met a jour le doc_type sur le parser et extrait le contexte OCR
        pour pre-remplir les champs de l'etape 2.
        """
        self.ensure_one()
        if not self.doc_type:
            raise UserError(_("Veuillez selectionner le type de document avant de continuer."))

        # Mettre a jour le type sur le parser (declenche l'apprentissage via write())
        self.parser_id.write({'doc_type': self.doc_type})

        self.write({'wizard_step': 'params'})
        # Rouvrir le wizard pour afficher l'etape 2
        return {
            'type':      'ir.actions.act_window',
            'name':      'Classification OCR — Etape 2',
            'res_model': self._name,
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    def action_back(self):
        """Retour etape 2 → etape 1."""
        self.ensure_one()
        self.write({'wizard_step': 'identify'})
        return {
            'type':      'ir.actions.act_window',
            'name':      'Classification OCR — Etape 1',
            'res_model': self._name,
            'res_id':    self.id,
            'view_mode': 'form',
            'target':    'new',
        }

    # ── Validation finale ─────────────────────────────────────────────────────

    def action_confirm(self):
        """
        Etape 2 — Validation finale.

        1. Resoudre / creer le client si demande
        2. Mettre a jour les donnees OCR sur le parser avec les valeurs confirmees
        3. Lancer l'extraction OCR avec le type correct
        4. L'apprentissage a deja ete declenche par parser.write({'doc_type': ...})
           dans action_next_step() → on renforce avec le contexte metier complet
        """
        self.ensure_one()

        # ── 1. Resoudre le partenaire ─────────────────────────────────────────
        partner = self.partner_id
        if self.create_new_partner and self.new_partner_name:
            partner = self._create_partner()

        # ── 2. Mettre a jour le contexte OCR sur le parser ────────────────────
        update_vals = {
            'doc_type':       self.doc_type,
            'ocr_compagnie':  self.company_ins_id.name if self.company_ins_id else False,
            'ocr_num_police': self.num_police or False,
            'ocr_montant':    self.montant or 0.0,
        }
        if self.doc_type == 'reglement':
            update_vals.update({
                'ocr_num_cheque': self.num_cheque or False,
                'ocr_banque':     self.bank_id.name if self.bank_id else False,
                'ocr_type_reg':   self.type_reg or 'C',
                'ocr_date_reg':   self.date_doc or False,
            })
        elif self.doc_type == 'avenant':
            update_vals['ocr_type_avenant'] = self.type_avenant or False
        elif self.doc_type == 'sinistre':
            update_vals['ocr_type_sinistre'] = self.type_sinistre or False
            update_vals['ocr_date_sinistre']  = self.date_sinistre or False

        self.parser_id.write(update_vals)

        # ── 3. Renforcer l'apprentissage avec contexte metier complet ─────────
        self._reinforce_learning()

        # ── 4. Lancer la creation de la piece via l'extraction OCR ───────────
        if self.parser_id.attachment_id:
            try:
                self.parser_id.write({'state': 'processing'})
                self.parser_id._mock_ocr_extract(self.parser_id.attachment_id.id)
            except Exception as exc:
                self.parser_id.write({
                    'state': 'error',
                    'error_message': str(exc),
                })
                raise UserError(
                    _("Erreur lors de la creation de la piece : %s") % str(exc)
                )

        # ── 5. Lier le partenaire si resolu ───────────────────────────────────
        if partner:
            piece = (
                self.parser_id.policy_id or
                self.parser_id.receipt_id or
                self.parser_id.settlement_id or
                self.parser_id.operation_id or
                self.parser_id.claim_id
            )
            if piece and hasattr(piece, 'partner_id'):
                try:
                    piece.write({'partner_id': partner.id})
                except Exception:
                    pass

        _logger.info(
            'AssurCore OCR Classify Wizard: parser[%d] classe en "%s" — piece creee.',
            self.parser_id.id, self.doc_type,
        )

        return {'type': 'ir.actions.act_window_close'}

    # ── Methodes internes ─────────────────────────────────────────────────────

    def _create_partner(self):
        """Cree un nouveau res.partner depuis les champs new_partner_*."""
        vals = {
            'name':          self.new_partner_name,
            'is_company':    self.new_partner_type == 'company',
            'customer_rank': 1,
        }
        if self.new_partner_cin:
            vals['cin'] = self.new_partner_cin
        if self.new_partner_mf:
            vals['matricule_fiscal'] = self.new_partner_mf
        partner = self.env['res.partner'].create(vals)
        _logger.info(
            'AssurCore OCR Classify: nouveau partenaire cree "%s" (id=%d)',
            partner.name, partner.id,
        )
        return partner

    def _reinforce_learning(self):
        """
        Renforce la table d'apprentissage avec le contexte metier complet
        valide par l'operateur (source='user', poids maximum).
        """
        subject   = self.parser_id.source_subject or self.parser_id.name or ''
        filename  = (self.parser_id.attachment_id.name
                     if self.parser_id.attachment_id else '')
        full_text = subject + ' ' + filename

        training = self.env['insurance.ocr.training']
        keywords = training.extract_keywords(full_text)
        if not keywords:
            return

        # Contexte metier complet confirme par l'operateur
        ctx = {}
        if self.company_ins_id:
            ctx['company_ins_id'] = self.company_ins_id.id
        if self.bank_id:
            ctx['bank_id'] = self.bank_id.id
        if self.doc_type == 'contrat':
            ctx['insurance_branch'] = 'auto'  # hypothese branche principale
        # Completer avec la detection automatique du texte
        auto_ctx = training.extract_context(full_text)
        for k, v in auto_ctx.items():
            if k not in ctx and v:
                ctx[k] = v

        training.learn(
            keywords,
            self.doc_type,
            source='user',
            parser_id=self.parser_id.id,
            context=ctx,
        )
        _logger.info(
            'AssurCore OCR Learning [wizard]: "%s" → %s (%d mots-cles, ctx=%s)',
            subject[:50], self.doc_type, len(keywords), list(ctx.keys()),
        )
