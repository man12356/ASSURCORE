# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Wizard de VENTILATION d'un reglement sur les operations d'une memoire
#
#  Ergonomie :
#   - depuis la fiche reglement : bouton « Ventiler sur operations »
#   - choisir la memoire -> les lignes ne proposent QUE ses operations
#   - montant pre-rempli = reste du de l'operation, plafonne au restant
#     non impute du reglement ; bouton « Tout ventiler » pour toutes les
#     operations de la memoire (FIFO par date)
#  Controles :
#   - montant ligne <= reste du de l'operation
#   - somme des lignes <= restant non impute du reglement
#  Concurrence :
#   - a la confirmation : verrou SELECT ... FOR UPDATE NOWAIT sur le
#     reglement + revalidation des restants en base (deux utilisateurs ne
#     peuvent pas sur-imputer le meme reglement simultanement)
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
import psycopg2

PRECISION = 3


class InsuranceOperationResidual(models.Model):
    _inherit = 'insurance.operation'

    def _due_amount(self):
        self.ensure_one()
        return (self.montant_prime or 0.0) + (self.montant_honoraire_ht or 0.0) \
            + (self.montant_tva or 0.0)

    def _residual_amount(self):
        """Reste du de l'operation = du - imputations actives."""
        self.ensure_one()
        paid = sum(self.allocation_ids.filtered(
            lambda l: l.settlement_id.state not in ('impaye', 'remplace')
        ).mapped('montant_impute'))
        return max(self._due_amount() - paid, 0.0)


class InsuranceVentilationWizard(models.TransientModel):
    _name = 'insurance.ventilation.wizard'
    _description = 'Ventilation d\'un règlement sur les opérations d\'une mémoire'

    settlement_id = fields.Many2one(
        'insurance.settlement', string='Règlement', required=True,
        default=lambda self: self.env.context.get('active_id'),
        domain=[('state', 'in', ('regle', 'encaisse'))],
    )
    currency_id = fields.Many2one(related='settlement_id.currency_id')
    partner_id = fields.Many2one(related='settlement_id.partner_id',
                                 string='Payeur')
    montant_reg = fields.Monetary(related='settlement_id.montant_reg',
                                  string='Montant règlement')
    restant_reglement = fields.Monetary(
        string='Restant non imputé', compute='_compute_restant',
        currency_field='currency_id',
        help='Montant du règlement non encore imputé (avant cette ventilation).',
    )
    total_ventile = fields.Monetary(
        string='Total de cette ventilation', compute='_compute_restant',
        currency_field='currency_id',
    )
    receipt_id = fields.Many2one(
        'insurance.receipt', string='Mémoire',
        help='Les lignes ne proposent que les opérations de cette mémoire.',
    )
    line_ids = fields.One2many(
        'insurance.ventilation.wizard.line', 'wizard_id', string='Ventilation')

    @api.depends('settlement_id', 'line_ids.montant')
    def _compute_restant(self):
        for wiz in self:
            deja = sum(wiz.settlement_id.imputation_ids.mapped('montant_impute'))
            wiz.total_ventile = sum(wiz.line_ids.mapped('montant'))
            wiz.restant_reglement = (wiz.settlement_id.montant_reg or 0.0) - deja

    @api.onchange('receipt_id')
    def _onchange_receipt(self):
        self.line_ids = [(5, 0, 0)]

    def action_fill_all(self):
        """Ajoute toutes les operations de la memoire avec reste du > 0,
        montants auto plafonnes au restant du reglement (FIFO par date)."""
        self.ensure_one()
        if not self.receipt_id:
            raise UserError(_('Choisissez d\'abord une mémoire.'))
        budget = self.restant_reglement - self.total_ventile
        deja_ops = self.line_ids.mapped('operation_id')
        lines = []
        ops = self.receipt_id.operation_ids.sorted(
            key=lambda o: (o.date_op or fields.Date.today(), o.id))
        for op in ops:
            if op in deja_ops or budget <= 0.0005:
                continue
            reste = op._residual_amount()
            if reste <= 0.0005:
                continue
            montant = min(reste, budget)
            budget -= montant
            lines.append((0, 0, {'operation_id': op.id, 'montant': montant}))
        if not lines:
            raise UserError(_(
                'Aucune opération à ventiler : tout est déjà réglé ou le '
                'restant du règlement est épuisé.'))
        self.line_ids = lines
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    # ── Confirmation avec VERROU anti-concurrence ─────────────────────────────

    def action_confirmer(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_('Ajoutez au moins une ligne de ventilation.'))

        # 1. VERROU sur le reglement (NOWAIT : echec immediat si un autre
        #    utilisateur est en train d'imputer le meme reglement)
        try:
            self.env.cr.execute(
                'SELECT id FROM insurance_settlement WHERE id = %s '
                'FOR UPDATE NOWAIT', (self.settlement_id.id,))
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_(
                'Ce règlement est en cours d\'imputation par un autre '
                'utilisateur. Réessayez dans quelques instants.'))

        # 2. Revalidation EN BASE apres verrou (les restants ont pu changer)
        self.settlement_id.invalidate_recordset()
        deja = sum(self.settlement_id.imputation_ids.mapped('montant_impute'))
        restant = (self.settlement_id.montant_reg or 0.0) - deja
        total = sum(self.line_ids.mapped('montant'))
        if float_compare(total, restant, precision_digits=PRECISION) > 0:
            raise ValidationError(_(
                'Le total ventilé (%(t).3f TND) dépasse le restant non imputé '
                'du règlement (%(r).3f TND) — il a peut-être été imputé par un '
                'autre utilisateur entre-temps.', t=total, r=restant))

        Imputation = self.env['insurance.settlement.imputation']
        for line in self.line_ids:
            if line.montant <= 0:
                raise ValidationError(_('Les montants doivent être positifs.'))
            line.operation_id.invalidate_recordset()
            reste_op = line.operation_id._residual_amount()
            if float_compare(line.montant, reste_op,
                             precision_digits=PRECISION) > 0:
                raise ValidationError(_(
                    'Opération %(op)s : le montant saisi (%(m).3f) dépasse son '
                    'reste dû (%(r).3f).',
                    op=line.operation_id.name, m=line.montant, r=reste_op))
            existing = Imputation.search([
                ('settlement_id', '=', self.settlement_id.id),
                ('operation_id', '=', line.operation_id.id),
                ('is_reconstructed', '=', False),
            ], limit=1)
            if existing:
                existing.write({
                    'montant_impute': existing.montant_impute + line.montant,
                    'date_imputation': fields.Date.today(),
                })
            else:
                Imputation.create({
                    'settlement_id': self.settlement_id.id,
                    'receipt_id': line.operation_id.receipt_id.id
                                  or self.receipt_id.id,
                    'operation_id': line.operation_id.id,
                    'montant_impute': line.montant,
                    'date_imputation': fields.Date.today(),
                })
        self.receipt_id._compute_amounts()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Ventilation enregistrée'),
                'message': _('%(n)d ligne(s), total %(t).3f TND imputés '
                             'depuis %(reg)s.', n=len(self.line_ids),
                             t=total, reg=self.settlement_id.name),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class InsuranceVentilationWizardLine(models.TransientModel):
    _name = 'insurance.ventilation.wizard.line'
    _description = 'Ligne de ventilation'

    wizard_id = fields.Many2one('insurance.ventilation.wizard',
                                required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    operation_id = fields.Many2one(
        'insurance.operation', string='Opération', required=True)
    reste_du = fields.Monetary(
        string='Reste dû opération', compute='_compute_reste',
        currency_field='currency_id')
    montant = fields.Monetary(string='Montant à imputer',
                              currency_field='currency_id')

    @api.depends('operation_id')
    def _compute_reste(self):
        for line in self:
            line.reste_du = (line.operation_id._residual_amount()
                             if line.operation_id else 0.0)

    @api.onchange('operation_id')
    def _onchange_operation(self):
        """Montant auto = reste du, plafonne au budget restant du reglement."""
        if not self.operation_id:
            return
        wiz = self.wizard_id
        autres = sum(l.montant for l in wiz.line_ids if l is not self)
        budget = max(wiz.restant_reglement - autres, 0.0)
        self.montant = min(self.operation_id._residual_amount(), budget)

    @api.onchange('montant')
    def _onchange_montant(self):
        if self.operation_id and self.montant:
            reste = self.operation_id._residual_amount()
            if float_compare(self.montant, reste, precision_digits=3) > 0:
                self.montant = reste
                return {'warning': {
                    'title': _('Montant plafonné'),
                    'message': _('Le montant ne peut pas dépasser le reste dû '
                                 'de l\'opération (%(r).3f TND).', r=reste)}}
