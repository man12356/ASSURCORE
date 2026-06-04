# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.settlement.imputation — Lettrage / Imputation d'un règlement
#  sur une ou plusieurs quittances (multi-quittances)
#
#  Concept métier :
#    Un seul chèque / virement peut couvrir plusieurs quittances :
#      - D'un même client (ex : renouvellement annuel en plusieurs fois)
#      - D'une famille (père → quittances épouse + enfants)
#    Le montant total du règlement est ventilé en lignes d'imputation,
#    chacune liée à une quittance précise.
#
#  Équivalent Oracle : PR_COMPENSATION_REGLEMENT
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class InsuranceSettlementImputation(models.Model):
    """
    Ligne d'imputation : fraction d'un règlement appliquée sur une quittance.

    Un règlement (insurance.settlement) peut avoir plusieurs lignes d'imputation.
    La somme des montants imputés ne peut pas dépasser le montant du règlement.
    """

    _name        = 'insurance.settlement.imputation'
    _description = 'Imputation de Règlement sur Quittance'
    _order       = 'date_imputation desc, id desc'
    _rec_name    = 'name'

    # ── Identification ─────────────────────────────────────────────────────────

    name = fields.Char(
        string='Référence',
        compute='_compute_name',
        store=True,
        help='Référence automatique : REG-xxx → QUITT-yyy',
    )

    # ── Relations principales ──────────────────────────────────────────────────

    settlement_id = fields.Many2one(
        comodel_name='insurance.settlement',
        string='Règlement',
        required=True,
        ondelete='cascade',
        index=True,
        help='Règlement (chèque, virement, espèces) source de l\'imputation.',
    )

    receipt_id = fields.Many2one(
        comodel_name='insurance.receipt',
        string='Quittance',
        required=True,
        ondelete='cascade',
        index=True,
        help='Quittance sur laquelle ce montant est imputé.',
    )

    # ── Montants ───────────────────────────────────────────────────────────────

    currency_id = fields.Many2one(
        related='settlement_id.currency_id',
        readonly=True,
    )

    montant_impute = fields.Monetary(
        string='Montant imputé (TND)',
        currency_field='currency_id',
        required=True,
        help='Fraction du règlement appliquée sur cette quittance.',
    )

    # ── Dates et traçabilité ───────────────────────────────────────────────────

    date_imputation = fields.Date(
        string='Date d\'imputation',
        required=True,
        default=fields.Date.today,
    )

    notes = fields.Text(string='Notes')

    # ── Champs liés (lecture seule) ────────────────────────────────────────────

    partner_id = fields.Many2one(
        related='settlement_id.partner_id',
        string='Payeur',
        readonly=True,
        store=True,
    )

    receipt_partner_id = fields.Many2one(
        related='receipt_id.partner_id',
        string='Assuré',
        readonly=True,
    )

    receipt_amount_total = fields.Monetary(
        related='receipt_id.amount_total',
        string='Total quittance (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    settlement_montant_reg = fields.Monetary(
        related='settlement_id.montant_reg',
        string='Montant règlement (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    settlement_state = fields.Selection(
        related='settlement_id.state',
        string='État règlement',
        readonly=True,
    )

    # ── Compute ────────────────────────────────────────────────────────────────

    @api.depends('settlement_id', 'receipt_id')
    def _compute_name(self):
        for rec in self:
            s = rec.settlement_id.name or '?'
            r = rec.receipt_id.name or '?'
            rec.name = f'{s} → {r}'

    # ── Contraintes ────────────────────────────────────────────────────────────

    @api.constrains('montant_impute')
    def _check_montant_positif(self):
        for rec in self:
            if rec.montant_impute <= 0:
                raise ValidationError(
                    _('Le montant imputé doit être positif.')
                )

    @api.constrains('montant_impute', 'settlement_id')
    def _check_montant_impute(self):
        """Le total des imputations ne peut pas dépasser le montant du règlement."""
        for rec in self:
            if not rec.settlement_id:
                continue
            total_impute = sum(
                rec.settlement_id.imputation_ids.mapped('montant_impute')
            )
            if total_impute > rec.settlement_id.montant_reg + 0.001:
                raise ValidationError(_(
                    'Le total des imputations (%(total).3f TND) dépasse '
                    'le montant du règlement (%(reg).3f TND).',
                    total=total_impute,
                    reg=rec.settlement_id.montant_reg,
                ))


# ==============================================================================
#  Wizard : Imputer un règlement existant sur une quittance
# ==============================================================================

class InsuranceImputationWizard(models.TransientModel):
    """
    Assistant d'imputation :
    Permet de sélectionner un règlement existant (avec solde disponible)
    et d'imputer tout ou partie de son montant restant sur la quittance courante.
    """

    _name        = 'insurance.imputation.wizard'
    _description = 'Assistant d\'Imputation de Règlement'

    # ── Contexte ───────────────────────────────────────────────────────────────

    receipt_id = fields.Many2one(
        comodel_name='insurance.receipt',
        string='Quittance',
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('active_id'),
    )

    receipt_amount_total = fields.Monetary(
        related='receipt_id.amount_total',
        string='Total quittance (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    receipt_amount_paid = fields.Monetary(
        related='receipt_id.amount_paid',
        string='Déjà encaissé (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    receipt_amount_residual = fields.Monetary(
        related='receipt_id.amount_residual',
        string='Reste à régler (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    # ── Sélection du règlement ─────────────────────────────────────────────────

    settlement_id = fields.Many2one(
        comodel_name='insurance.settlement',
        string='Règlement à imputer',
        required=True,
        domain=[('state', 'in', ('regle', 'encaisse')), ('montant_restant', '>', 0)],
        help='Sélectionnez un règlement ayant un solde disponible.',
    )

    settlement_montant_reg = fields.Monetary(
        related='settlement_id.montant_reg',
        string='Montant total règlement (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    settlement_montant_restant = fields.Monetary(
        related='settlement_id.montant_restant',
        string='Solde disponible (TND)',
        readonly=True,
        currency_field='currency_id',
    )

    settlement_partner_id = fields.Many2one(
        related='settlement_id.partner_id',
        string='Payeur',
        readonly=True,
    )

    # ── Montant à imputer ──────────────────────────────────────────────────────

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        default=lambda self: self.env.ref('base.TND', raise_if_not_found=False)
                             or self.env.company.currency_id,
        readonly=True,
    )

    montant_a_imputer = fields.Monetary(
        string='Montant à imputer (TND)',
        currency_field='currency_id',
        required=True,
        help='Montant à prélever sur le solde du règlement pour régler cette quittance.',
    )

    date_imputation = fields.Date(
        string='Date d\'imputation',
        required=True,
        default=fields.Date.today,
    )

    notes = fields.Text(string='Notes')

    # ── Onchange pour pré-remplir le montant ───────────────────────────────────

    @api.onchange('settlement_id', 'receipt_id')
    def _onchange_settlement(self):
        if self.settlement_id and self.receipt_id:
            # Proposer le minimum entre le solde du règlement et le reste dû
            reste_quittance = self.receipt_id.amount_residual or 0
            solde_reglement = self.settlement_id.montant_restant or 0
            self.montant_a_imputer = min(reste_quittance, solde_reglement)

    # ── Action de confirmation ─────────────────────────────────────────────────

    def action_confirmer_imputation(self):
        """Crée la ligne d'imputation et met à jour les soldes."""
        self.ensure_one()

        if not self.settlement_id:
            raise UserError(_('Veuillez sélectionner un règlement.'))

        if self.montant_a_imputer <= 0:
            raise UserError(_('Le montant à imputer doit être positif.'))

        if self.montant_a_imputer > self.settlement_id.montant_restant + 0.001:
            raise UserError(_(
                'Le montant à imputer (%(a).3f TND) dépasse le solde '
                'disponible du règlement (%(b).3f TND).',
                a=self.montant_a_imputer,
                b=self.settlement_id.montant_restant,
            ))

        # Créer la ligne d'imputation
        self.env['insurance.settlement.imputation'].create({
            'settlement_id':  self.settlement_id.id,
            'receipt_id':     self.receipt_id.id,
            'montant_impute': self.montant_a_imputer,
            'date_imputation': self.date_imputation,
            'notes':          self.notes,
        })

        # Recalculer les montants de la quittance
        self.receipt_id._compute_amounts()

        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   _('Imputation créée'),
                'message': _(
                    '%(montant).3f TND imputés depuis le règlement %(reg)s.',
                    montant=self.montant_a_imputer,
                    reg=self.settlement_id.name,
                ),
                'type':    'success',
                'sticky':  False,
            },
        }
