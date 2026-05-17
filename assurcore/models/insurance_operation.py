# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.operation — Opération / Avenant sur Police d'Assurance
#
#  Ex-table Oracle : PR_OPERATION
#  Champs clés : NUM_OPERATION, CODE_OPERATION1..4, TYPE_CLIENT, NUM_CLIENT,
#                COMPAGNIE, NUM_POLICE, DESIGNATION, DATE_OP, DATE_VALIDITE_DU,
#                DATE_VALIDITE_AU, MONTANT_PRIME, COMMISSION, NATURE, T_C
#
#  Une opération représente tout événement contractuel lié à une police :
#    - Émission initiale (nouveau contrat)
#    - Renouvellement annuel
#    - Avenant (modification de garanties, de véhicule, d'usage…)
#    - Suspension temporaire
#    - Annulation / Résiliation
#
#  Chaque opération peut générer une quittance (insurance.receipt) si elle
#  implique un encaissement supplémentaire ou un remboursement.
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

CODE_OPERATION = [
    ('EMI', 'Émission initiale'),
    ('REN', 'Renouvellement'),
    ('AVN', 'Avenant de modification'),
    ('SUS', 'Suspension'),
    ('ANN', 'Annulation'),
    ('RES', 'Résiliation'),
    ('REM', 'Remise en vigueur'),
    ('CES', 'Cession de contrat'),
]

NATURE_OPERATION = [
    ('R', 'Renouvellement'),
    ('N', 'Nouveau contrat'),
    ('A', 'Avenant'),
    ('S', 'Sinistre — honoraires'),
    ('F', 'Frais / Facturation'),
]

TYPE_CONTRAT = [
    ('T', 'Tiers (portefeuille client)'),
    ('P', 'Propre (assurance interne)'),
]

OPERATION_STATE = [
    ('draft',     'Brouillon'),
    ('confirmed', 'Confirmée'),
    ('invoiced',  'Facturée'),
    ('canceled',  'Annulée'),
]


class InsuranceOperation(models.Model):
    """
    Opération sur police d'assurance (avenant, annulation, renouvellement…).

    Correspond aux enregistrements de PR_OPERATION dans l'Oracle ASSKAREKAMOUN.
    La clé composite Oracle (TYPE_CLIENT + NUM_CLIENT + ATTRIBUT_CLIENT) est
    remplacée par le Many2one policy_id → insurance.policy.

    Chaque opération peut être liée à une quittance (insurance.receipt)
    si elle génère un flux financier.
    """

    _name = 'insurance.operation'
    _description = 'Opération / Avenant sur Police'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_op desc, name desc'
    _rec_name = 'name'

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='N° Opération',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'insurance.operation'
        ) or '/',
        tracking=True,
        help='Référence séquentielle AssurCore. Ex : OP/2026/00421. '
             'Ex-champ Oracle : NUM_OPERATION NUMBER(33,0) dans PR_OPERATION.',
    )

    state = fields.Selection(
        selection=OPERATION_STATE,
        string='État',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )

    # ── Code opération (Matrice Oracle CODE_OPERATION1..4) ─────────────────────
    # L'ancien système utilisait jusqu'à 4 codes opération cumulables.
    # Dans Odoo, on simplifie avec un code principal + un code secondaire.

    code_operation = fields.Selection(
        selection=CODE_OPERATION,
        string='Type d\'opération',
        required=True,
        tracking=True,
        default='REN',
        help='Type principal d\'opération. '
             'Ex-champ Oracle : CODE_OPERATION1 CHAR(3) dans PR_OPERATION.',
    )

    code_operation_2 = fields.Selection(
        selection=CODE_OPERATION,
        string='Type secondaire',
        help='Opération combinée (rare). '
             'Ex-champ Oracle : CODE_OPERATION2 dans PR_OPERATION.',
    )

    # ── Police parente ─────────────────────────────────────────────────────────

    policy_id = fields.Many2one(
        comodel_name='insurance.policy',
        string='Police',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Police sur laquelle porte cette opération.',
    )

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client / Assuré',
        related='policy_id.partner_id',
        store=True,
    )

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        related='policy_id.company_ins_id',
        store=True,
    )

    branche = fields.Selection(
        related='policy_id.branche',
        store=True,
        string='Branche',
    )

    agence_courtier = fields.Char(
        related='policy_id.agence_courtier',
        store=True,
        string='Agence',
    )

    # ── Dates ─────────────────────────────────────────────────────────────────

    date_op = fields.Date(
        string='Date d\'opération',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Ex-champ Oracle : DATE_OP DATE dans PR_OPERATION.',
    )

    date_validite_du = fields.Date(
        string='Couverture du',
        help='Début de la nouvelle période de couverture après avenant. '
             'Ex-champ Oracle : DATE_VALIDITE_DU dans PR_OPERATION.',
    )

    date_validite_au = fields.Date(
        string='Couverture au',
        help='Fin de la période de couverture. '
             'Ex-champ Oracle : DATE_VALIDITE_AU dans PR_OPERATION.',
    )

    date_echeance = fields.Date(
        string='Date d\'échéance quittance',
        help='Ex-champ Oracle : DATE_ECHEANCE dans PR_OPERATION.',
    )

    # ── Désignation & Véhicule ────────────────────────────────────────────────

    designation = fields.Char(
        string='Désignation',
        size=250,
        help='Libellé de l\'opération. '
             'Ex-champ Oracle : DESIGNATION VARCHAR2(250) dans PR_OPERATION.',
    )

    num_quittance = fields.Char(
        string='N° Quittance compagnie',
        size=30,
        help='Référence de la quittance chez la compagnie. '
             'Ex-champ Oracle : NUM_QUITTANCE VARCHAR2(30) dans PR_OPERATION.',
    )

    num_attestation = fields.Char(
        string='N° Attestation',
        size=20,
        help='Ex-champ Oracle : NUM_ATTESTATION VARCHAR2(20) dans PR_OPERATION.',
    )

    vehicule = fields.Char(
        string='Véhicule / Risque',
        size=30,
        help='Matricule tunisien ou désignation du risque assuré. '
             'Ex-champ Oracle : VEHICULE VARCHAR2(30) dans PR_OPERATION.',
    )

    nature = fields.Selection(
        selection=NATURE_OPERATION,
        string='Nature',
        default='R',
        help='Ex-champ Oracle : NATURE CHAR(1) DEFAULT \'R\' dans PR_OPERATION.',
    )

    type_contrat = fields.Selection(
        selection=TYPE_CONTRAT,
        string='Type',
        default='T',
        help='Ex-champ Oracle : T_C CHAR(1) DEFAULT \'T\' dans PR_OPERATION.',
    )

    avenant_rembourser = fields.Boolean(
        string='Avenant à rembourser',
        default=False,
        help='Si coché, cet avenant génère un remboursement au client. '
             'Ex-champ Oracle : AVENANT_REMBOURSER CHAR(1) dans PR_OPERATION.',
    )

    cxp = fields.Boolean(
        string='CXP (résiliation compagnie)',
        default=False,
        help='Ex-champ Oracle : CXP CHAR(1) DEFAULT \'N\' dans PR_OPERATION.',
    )

    # ── Montants financiers ────────────────────────────────────────────────────

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    montant_prime = fields.Monetary(
        string='Prime nette (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Ex-champ Oracle : MONTANT_PRIME NUMBER(11,3) dans PR_OPERATION.',
    )

    prime_echeance = fields.Monetary(
        string='Prime à l\'échéance (TND)',
        currency_field='currency_id',
        help='Ex-champ Oracle : PRIME_ECHEANCE NUMBER(11,3) dans PR_OPERATION.',
    )

    commission = fields.Monetary(
        string='Commission (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Commission courtier sur cette opération. '
             'Ex-champ Oracle : COMMISSION NUMBER(11,3) dans PR_OPERATION.',
    )

    montant_honoraire_ht = fields.Monetary(
        string='Honoraires HT (TND)',
        currency_field='currency_id',
        help='Ex-champ Oracle : MONTANT_HONORAIRE_HT NUMBER(11,3) dans PR_OPERATION.',
    )

    libelle_honoraire = fields.Char(
        string='Libellé honoraires',
        size=500,
        help='Ex-champ Oracle : LIBELLE_HONORAIRE VARCHAR2(500) dans PR_OPERATION.',
    )

    case_a_cocher_hon = fields.Boolean(
        string='Honoraires à facturer',
        default=False,
        help='Ex-champ Oracle : CASE_A_COCHER_HON CHAR(1) DEFAULT \'N\'.',
    )

    case_a_cocher_prime = fields.Boolean(
        string='Prime à facturer',
        default=False,
        help='Ex-champ Oracle : CASE_A_COCHER_PRIME CHAR(1) DEFAULT \'N\'.',
    )

    # ── Quittance générée ─────────────────────────────────────────────────────

    receipt_id = fields.Many2one(
        comodel_name='insurance.receipt',
        string='Quittance générée',
        readonly=True,
        copy=False,
        help='Quittance AssurCore créée automatiquement si l\'opération '
             'génère un flux financier.',
    )

    # ── Journée d\'encaissement ───────────────────────────────────────────────

    journal_enc_id = fields.Many2one(
        comodel_name='insurance.journal.enc',
        string='Journée d\'encaissement',
        readonly=True,
        copy=False,
        help='Journée d\'encaissement compagnie liée. '
             'Ex-champ Oracle : NUM_JOUR_ENC dans PR_OPERATION.',
    )

    # ── Métadonnées ───────────────────────────────────────────────────────────

    notes = fields.Text(string='Notes')
    supp_log = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    # ─────────────────────────────────────────────────────────────────────────
    #  Transitions
    # ─────────────────────────────────────────────────────────────────────────

    def action_confirm(self):
        """Brouillon → Confirmée."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Seules les opérations en Brouillon peuvent être confirmées.'))
            rec.write({'state': 'confirmed'})
            # Met à jour les dates de la police parente si avenant
            if rec.code_operation in ('AVN', 'REN') and rec.date_validite_au:
                rec.policy_id.write({'date_echeance': rec.date_validite_au})

    def action_generate_receipt(self):
        """Crée une quittance (insurance.receipt) depuis cette opération."""
        self.ensure_one()
        if self.receipt_id:
            raise UserError(_('Une quittance existe déjà pour cette opération.'))
        if not (self.montant_prime or self.montant_honoraire_ht):
            raise UserError(_(
                'Renseignez au moins un montant (prime ou honoraires) '
                'avant de générer la quittance.'
            ))

        receipt = self.env['insurance.receipt'].create({
            'policy_id': self.policy_id.id,
            'num_quittance_compagnie': self.num_quittance,
            'num_attestation': self.num_attestation,
            'date_emission': self.date_op,
            'date_echeance': self.date_echeance or self.date_validite_au,
            'date_validite_du': self.date_validite_du,
            'date_validite_au': self.date_validite_au,
            'montant_prime': self.montant_prime,
            'commission': self.commission,
            'montant_honoraire_ht': self.montant_honoraire_ht,
            'designation': self.designation,
            'vehicule': self.vehicule,
            'nature': self.nature,
            'type_client_op': self.type_contrat,
        })
        self.write({'receipt_id': receipt.id, 'state': 'invoiced'})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quittance générée'),
            'res_model': 'insurance.receipt',
            'view_mode': 'form',
            'res_id': receipt.id,
        }

    def action_cancel(self):
        """→ Annulée."""
        for rec in self:
            if rec.receipt_id and rec.receipt_id.state in ('encaissee', 'reversee'):
                raise UserError(_(
                    'La quittance liée à cette opération est déjà encaissée. '
                    'Impossible d\'annuler l\'opération.'
                ))
            rec.write({'state': 'canceled'})

    # ─────────────────────────────────────────────────────────────────────────
    #  Contraintes
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('date_validite_du', 'date_validite_au')
    def _check_dates(self):
        for rec in self:
            if rec.date_validite_du and rec.date_validite_au:
                if rec.date_validite_au < rec.date_validite_du:
                    raise ValidationError(_(
                        'La date de fin de couverture doit être '
                        'postérieure à la date de début.'
                    ))

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == '/':
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('insurance.operation') or '/'
            )
        return super().create(vals)

    def name_get(self):
        result = []
        op_labels = dict(CODE_OPERATION)
        for rec in self:
            label = op_labels.get(rec.code_operation, rec.code_operation)
            name = f'{rec.name} ({label})'
            if rec.policy_id:
                name += ' — ' + rec.policy_id.num_police
            result.append((rec.id, name))
        return result
