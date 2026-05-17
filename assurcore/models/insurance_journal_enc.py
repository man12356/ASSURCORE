# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.journal.enc — Journée d'Encaissement Compagnie
#  Ex-table Oracle : PR_JOUR_ENC
#
#  Chaque journée regroupe toutes les opérations encaissées pour une
#  compagnie donnée sur une date. Elle sert de base au bordereau de
#  reversement envoyé à la compagnie.
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InsuranceJournalEnc(models.Model):
    """
    Journée d'encaissement : regroupement quotidien des primes encaissées
    pour une compagnie, servant à générer le bordereau de reversement.
    Équivalent Oracle : PR_JOUR_ENC (NUM_JOUR_ENC, COMPAGNIE, DATE_CREATION…).
    """

    _name        = 'insurance.journal.enc'
    _description = 'Journée d\'Encaissement'
    _inherit     = ['mail.thread']
    _order       = 'date_creation desc, name desc'
    _rec_name    = 'name'

    STATE = [
        ('ouvert',   'Ouverte'),
        ('envoye',   'Envoyée à la compagnie'),
        ('regle',    'Réglée'),
        ('cloture',  'Clôturée'),
    ]

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='N° Journée',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'insurance.journal.enc'
        ) or '/',
        tracking=True,
        help='Référence séquentielle. Ex : JE/2026/001. '
             'Ex-champ Oracle : NUM_JOUR_ENC NUMBER(33,0) dans PR_JOUR_ENC.',
    )

    state = fields.Selection(
        selection=STATE,
        string='État',
        default='ouvert',
        required=True,
        tracking=True,
    )

    # ── Compagnie & Date ───────────────────────────────────────────────────────

    company_ins_id = fields.Many2one(
        comodel_name='insurance.company',
        string='Compagnie',
        required=True,
        ondelete='restrict',
        tracking=True,
        index=True,
        help='Ex-champ Oracle : COMPAGNIE VARCHAR2(30) dans PR_JOUR_ENC.',
    )

    date_creation = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Ex-champ Oracle : DATE_CREATION DATE dans PR_JOUR_ENC.',
    )

    # ── Montants ───────────────────────────────────────────────────────────────

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    total_montant_enc = fields.Monetary(
        string='Total encaissé (TND)',
        currency_field='currency_id',
        tracking=True,
        help='Ex-champ Oracle : TOTAL_MONTANT_ENC NUMBER(11,3) dans PR_JOUR_ENC.',
    )

    total_jour_commission = fields.Monetary(
        string='Total commission (TND)',
        currency_field='currency_id',
        help='Ex-champ Oracle : TOTAL_JOUR_COMMISSION NUMBER(11,3).',
    )

    total_montant_enc_net = fields.Monetary(
        string='Net à reverser (TND)',
        currency_field='currency_id',
        compute='_compute_net',
        store=True,
        help='= Total encaissé − Commission. '
             'Ex-champ Oracle : TOTAL_MONTANT_ENC_NET NUMBER(11,3).',
    )

    @api.depends('total_montant_enc', 'total_jour_commission')
    def _compute_net(self):
        for rec in self:
            rec.total_montant_enc_net = rec.total_montant_enc - rec.total_jour_commission

    # ── Règlement de la journée ────────────────────────────────────────────────

    montant_reg_enc = fields.Monetary(
        string='Règlement encaissement (TND)',
        currency_field='currency_id',
        help='Ex-champ Oracle : MONTANT_REG_ENC.',
    )

    date_reg_enc = fields.Date(string='Date règlement encaissement')

    type_reg_enc = fields.Selection(
        selection=[('C', 'Chèque'), ('E', 'Espèces'), ('V', 'Virement')],
        string='Mode règlement',
        default='C',
    )

    num_cheque_enc = fields.Char(string='N° Chèque', size=30)
    banque_enc = fields.Char(string='Banque', size=50)

    # ── Métadonnées ────────────────────────────────────────────────────────────

    notes = fields.Text(
        string='Notes',
        help='Ex-champ Oracle : NOTES VARCHAR2(250) dans PR_JOUR_ENC.',
    )

    agence_courtier = fields.Char(
        string='Agence',
        size=30,
        default=lambda self: self.env.company.name,
    )

    # ── Transitions ────────────────────────────────────────────────────────────

    def action_envoyer(self):
        self.write({'state': 'envoye'})

    def action_regler(self):
        self.write({'state': 'regle'})

    def action_cloturer(self):
        for rec in self:
            if rec.state != 'regle':
                raise UserError(_('La journée doit être réglée avant clôture.'))
        self.write({'state': 'cloture'})

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == '/':
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('insurance.journal.enc') or '/'
            )
        return super().create(vals)
