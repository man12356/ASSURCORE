# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Lot 1 : Granularité d'imputation règlement ↔ opération
#  Réf. : SPEC_Imputation_Operation_Graphe_Navigation.md (§2.1 à §2.4)
#
#  Architecture retenue (constat sur l'existant EVO01) :
#    - insurance.settlement.imputation (EVO01) lettre déjà règlement ↔ quittance,
#      et chaque quittance (insurance.receipt) est générée 1-1 depuis une
#      opération (insurance.operation.receipt_id).
#    - EVO02 ÉTEND ce modèle au lieu d'en créer un doublon :
#        * operation_id      → granularité opération (stocké, pour graphe/recherche)
#        * is_third_party    → paiement pour compte de tiers (payeur ≠ assuré)
#        * is_reconstructed  → ventilation reconstituée par la migration (FIFO)
#        * contraintes C2 (non sur-règlement), C3 (opération facturée non annulée),
#          C5 (cohérence devise) — C1 (non sur-imputation) existait en EVO01.
#    - insurance.operation.settlement_state → statut de règlement dérivé (§2.4)
#
#  Les contraintes s'appliquent aux saisies NOUVELLES uniquement :
#    - lignes is_reconstructed=True : exemptées (historique migré tel quel)
#    - contexte evo02_skip_checks=True : réservé aux scripts de migration
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare

PRECISION = 3  # TND : 3 décimales (millimes)


class InsuranceSettlementImputationEvo02(models.Model):
    _inherit = 'insurance.settlement.imputation'

    # ── EVO02 : granularité opération ──────────────────────────────────────────

    operation_id = fields.Many2one(
        comodel_name='insurance.operation',
        string='Opération',
        compute='_compute_operation_id',
        store=True,
        readonly=False,
        index=True,
        help='Opération (quittance compagnie) réglée par cette ligne. '
             'Déduite automatiquement de la quittance ; modifiable si la '
             'quittance regroupe plusieurs opérations.',
    )

    is_third_party = fields.Boolean(
        string='Paiement pour tiers',
        compute='_compute_is_third_party',
        store=True,
        help='Vrai si le payeur du règlement diffère du client de la quittance '
             '(époux/épouse, sociétés liées, groupements…). '
             'Équivalent Oracle : PR_REG_FACTURE.TIERS.',
    )

    is_reconstructed = fields.Boolean(
        string='Ventilation reconstituée',
        default=False,
        readonly=True,
        help='Ligne créée par la migration : la ventilation par opération a été '
             'reconstituée par règle FIFO et n\'est pas contractuelle. '
             'Exemptée des contraintes de cohérence.',
    )

    company_ins_id = fields.Many2one(
        related='operation_id.company_ins_id',
        string='Compagnie',
        store=True,
        readonly=True,
    )

    # ── Calculs ────────────────────────────────────────────────────────────────

    @api.depends('receipt_id')
    def _compute_operation_id(self):
        Operation = self.env['insurance.operation']
        for rec in self:
            if rec.operation_id and rec.operation_id.receipt_id == rec.receipt_id:
                continue  # déjà cohérent (saisie manuelle)
            rec.operation_id = Operation.search(
                [('receipt_id', '=', rec.receipt_id.id)], limit=1,
            ) if rec.receipt_id else False

    @api.onchange('operation_id')
    def _onchange_operation_evo02(self):
        """Ergonomie : choisir l'operation remplit la quittance et propose
        le montant = reste du de l'operation, plafonne au restant du
        reglement."""
        if not self.operation_id:
            return
        if self.operation_id.receipt_id:
            self.receipt_id = self.operation_id.receipt_id
        reste_op = self.operation_id._residual_amount()
        budget = reste_op
        if self.settlement_id:
            origin_id = self._origin.id if self._origin else False
            deja = sum(self.settlement_id.imputation_ids.filtered(
                lambda l: l.id != origin_id
            ).mapped('montant_impute'))
            budget = min(reste_op,
                         max((self.settlement_id.montant_reg or 0.0) - deja, 0.0))
        if not self.montant_impute:
            self.montant_impute = budget

    @api.onchange('montant_impute')
    def _onchange_montant_evo02(self):
        if self.operation_id and self.montant_impute and not self.is_reconstructed:
            reste = self.operation_id._residual_amount()
            if self.montant_impute > reste + 0.0005:
                self.montant_impute = reste
                return {'warning': {
                    'title': _('Montant plafonné'),
                    'message': _('Le montant ne peut pas dépasser le reste dû '
                                 'de l\'opération (%(r).3f TND).', r=reste)}}

    @api.depends('settlement_id.partner_id', 'receipt_id.partner_id')
    def _compute_is_third_party(self):
        for rec in self:
            payer = rec.settlement_id.partner_id
            insured = rec.receipt_id.partner_id
            rec.is_third_party = bool(payer and insured and payer != insured)

    # ── Contraintes EVO02 (saisies nouvelles uniquement) ───────────────────────

    def _evo02_checks_enabled(self):
        """Les contrôles sont désactivés pour l'historique migré."""
        return not (
            self.env.context.get('evo02_skip_checks')
            or self.is_reconstructed
        )

    @api.constrains('montant_impute', 'settlement_id')
    def _check_montant_impute(self):
        """Surcharge de la contrainte C1 d'EVO01 : ajoute l'exemption
        historique migré (is_reconstructed / evo02_skip_checks) — les
        3 règlements sur-imputés Oracle doivent rester modifiables par
        la ventilation FIFO sans être bloqués."""
        for rec in self:
            if not rec._evo02_checks_enabled() or not rec.settlement_id:
                continue
            lines = rec.settlement_id.imputation_ids.filtered(
                lambda l: not l.is_reconstructed)
            total = sum(lines.mapped('montant_impute'))
            if float_compare(total, rec.settlement_id.montant_reg,
                             precision_digits=PRECISION) > 0:
                raise ValidationError(_(
                    'Le total des imputations (%(total).3f TND) dépasse '
                    'le montant du règlement (%(reg).3f TND).',
                    total=total, reg=rec.settlement_id.montant_reg,
                ))

    @api.constrains('montant_impute', 'receipt_id')
    def _check_receipt_overpayment(self):
        """C2 — Non sur-règlement : total imputé sur la quittance ≤ total dû.

        Anomalie Oracle corrigée : 29 mémoires sur-réglées (rapport 11/06/2026).
        Les lignes de règlements impayés/remplacés ne comptent pas.
        """
        for rec in self:
            if not rec._evo02_checks_enabled() or not rec.receipt_id:
                continue
            lines = rec.receipt_id.imputation_ids.filtered(
                lambda l: l.settlement_id.state not in ('impaye', 'remplace')
            )
            total = sum(lines.mapped('montant_impute'))
            if float_compare(total, rec.receipt_id.amount_total,
                             precision_digits=PRECISION) > 0:
                raise ValidationError(_(
                    'Sur-règlement refusé : le total imputé sur la quittance '
                    '%(rcpt)s atteindrait %(total).3f TND pour un dû de '
                    '%(due).3f TND.\n'
                    'Si un règlement précédent est revenu impayé, marquez-le '
                    '« Impayé » avant de saisir son remplacement.',
                    rcpt=rec.receipt_id.name,
                    total=total,
                    due=rec.receipt_id.amount_total,
                ))

    @api.constrains('receipt_id', 'operation_id')
    def _check_operation_invoiced(self):
        """C3 — Une quittance dont l'opération est annulée (ou inexistante)
        ne peut pas être réglée (règle de gestion client n°4)."""
        for rec in self:
            if not rec._evo02_checks_enabled():
                continue
            op = rec.operation_id
            if op and op.state == 'canceled':
                raise ValidationError(_(
                    'Imputation refusée : l\'opération %(op)s liée à la '
                    'quittance %(rcpt)s est annulée.',
                    op=op.name, rcpt=rec.receipt_id.name,
                ))
            if op and op.receipt_id and op.receipt_id != rec.receipt_id:
                raise ValidationError(_(
                    'Incohérence : l\'opération %(op)s n\'appartient pas à la '
                    'quittance %(rcpt)s (une opération ne peut être rattachée '
                    'qu\'à une seule quittance/mémoire — règle n°5).',
                    op=op.name, rcpt=rec.receipt_id.name,
                ))

    @api.constrains('settlement_id', 'receipt_id')
    def _check_currency(self):
        """C5 — Cohérence de devise règlement / quittance."""
        for rec in self:
            if not rec._evo02_checks_enabled():
                continue
            cur_s = rec.settlement_id.currency_id
            cur_r = rec.receipt_id.currency_id
            if cur_s and cur_r and cur_s != cur_r:
                raise ValidationError(_(
                    'Devises incohérentes entre le règlement (%(a)s) et la '
                    'quittance (%(b)s).', a=cur_s.name, b=cur_r.name,
                ))

    @api.constrains('settlement_id', 'receipt_id')
    def _check_duplicate_line(self):
        """Une seule ligne par couple (règlement, quittance) : modifier la
        ligne existante plutôt qu'en empiler plusieurs (lisibilité lettrage)."""
        for rec in self:
            if not rec._evo02_checks_enabled():
                continue
            dup = self.search_count([
                ('id', '!=', rec.id),
                ('settlement_id', '=', rec.settlement_id.id),
                ('receipt_id', '=', rec.receipt_id.id),
                ('is_reconstructed', '=', False),
            ])
            if dup:
                raise ValidationError(_(
                    'Une imputation du règlement %(s)s sur la quittance %(r)s '
                    'existe déjà : modifiez son montant au lieu de créer une '
                    'seconde ligne.',
                    s=rec.settlement_id.name, r=rec.receipt_id.name,
                ))


class InsuranceOperationEvo02(models.Model):
    _inherit = 'insurance.operation'

    # ── EVO02 §2.4 : statut de règlement dérivé ───────────────────────────────

    SETTLEMENT_STATE = [
        ('non_facturee', 'Non facturée'),
        ('non_reglee',   'Non réglée'),
        ('partielle',    'Partiellement réglée'),
        ('soldee',       'Soldée'),
    ]

    settlement_state = fields.Selection(
        selection=SETTLEMENT_STATE,
        string='Règlement',
        compute='_compute_settlement_state',
        store=True,
        index=True,
        help='Second statut : situation de règlement de l\'opération, '
             'dérivée du lettrage de sa quittance.',
    )

    amount_paid_op = fields.Monetary(
        related='receipt_id.amount_paid',
        string='Encaissé (TND)',
        readonly=True,
    )

    amount_residual_op = fields.Monetary(
        related='receipt_id.amount_residual',
        string='Reste à régler (TND)',
        readonly=True,
    )

    allocation_ids = fields.One2many(
        comodel_name='insurance.settlement.imputation',
        inverse_name='operation_id',
        string='Imputations de règlements',
        help='Ventilation des règlements sur cette opération (EVO02).',
    )

    @api.depends('state', 'receipt_id', 'receipt_id.amount_total',
                 'receipt_id.amount_paid')
    def _compute_settlement_state(self):
        for rec in self:
            if not rec.receipt_id:
                rec.settlement_state = 'non_facturee'
            elif float_compare(rec.receipt_id.amount_paid, 0.0,
                               precision_digits=PRECISION) <= 0:
                rec.settlement_state = 'non_reglee'
            elif float_compare(rec.receipt_id.amount_paid,
                               rec.receipt_id.amount_total,
                               precision_digits=PRECISION) < 0:
                rec.settlement_state = 'partielle'
            else:
                rec.settlement_state = 'soldee'


class InsuranceReceiptEvo02(models.Model):
    _inherit = 'insurance.receipt'

    operation_ids = fields.One2many(
        comodel_name='insurance.operation',
        inverse_name='receipt_id',
        string='Opérations',
        help='Opérations (quittances compagnie) couvertes par cette quittance.',
    )

    payment_lead_days = fields.Integer(
        string='Délai de paiement (jours)',
        compute='_compute_payment_lead_days', store=True,
        group_operator='avg',
        help='Nombre de jours entre l\'émission de la mémoire et la dernière '
             'imputation qui la solde. Vide tant qu\'elle n\'est pas soldée.',
    )

    @api.depends('imputation_ids.montant_impute', 'imputation_ids.date_imputation',
                 'date_emission', 'montant_prime')
    def _compute_payment_lead_days(self):
        for rec in self:
            lines = rec.imputation_ids.filtered(
                lambda l: l.settlement_id.state not in ('impaye', 'remplace'))
            paid = sum(lines.mapped('montant_impute'))
            due = rec.montant_prime or 0.0
            if (rec.date_emission and lines and due > 0
                    and paid + 0.005 >= due):
                last = max(lines.mapped('date_imputation'))
                rec.payment_lead_days = max((last - rec.date_emission).days, 0)
            else:
                rec.payment_lead_days = False

    # ── Décision client 12/06/2026 : timbre fiscal OPTIONNEL ──────────────────
    apply_timbre_fiscal = fields.Boolean(
        string='Appliquer le timbre fiscal',
        default=True,
        help='Coché par défaut sur les nouvelles facturations : le timbre '
             'fiscal légal (1 DT) est intégré automatiquement. Décochez pour '
             'l\'exclure. Désactivé sur l\'historique migré (TOTAL_FACT '
             'Oracle l\'incluait déjà).',
    )

    @api.depends('apply_timbre_fiscal')
    def _compute_tax_rates(self):
        super()._compute_tax_rates()
        for rec in self:
            if not rec.apply_timbre_fiscal:
                rec.timbre_fiscal = 0.0


class InsuranceSettlementEvo02(models.Model):
    _inherit = 'insurance.settlement'

    montant_impute_total = fields.Monetary(
        string='Total imputé (TND)',
        compute='_compute_montant_impute_total',
        store=True,
        currency_field='currency_id',
    )

    is_fully_allocated = fields.Boolean(
        string='Imputé en totalité',
        compute='_compute_montant_impute_total',
        store=True,
    )

    has_third_party = fields.Boolean(
        string='Contient des imputations pour tiers',
        compute='_compute_has_third_party',
        store=True,
    )

    @api.depends('imputation_ids.montant_impute', 'montant_reg')
    def _compute_montant_impute_total(self):
        for rec in self:
            total = sum(rec.imputation_ids.mapped('montant_impute'))
            rec.montant_impute_total = total
            rec.is_fully_allocated = (
                float_compare(total, rec.montant_reg,
                              precision_digits=PRECISION) >= 0
                and bool(rec.imputation_ids)
            )

    @api.depends('imputation_ids.is_third_party')
    def _compute_has_third_party(self):
        for rec in self:
            rec.has_third_party = any(rec.imputation_ids.mapped('is_third_party'))


class InsuranceImputationWizardEvo02(models.TransientModel):
    _inherit = 'insurance.imputation.wizard'

    # ── EVO02 : confirmation explicite du paiement pour tiers ─────────────────

    is_third_party = fields.Boolean(
        string='Paiement pour tiers',
        compute='_compute_is_third_party',
        help='Le payeur du règlement sélectionné diffère du client de la quittance.',
    )

    confirm_third_party = fields.Boolean(
        string='Je confirme le paiement pour compte de tiers',
    )

    @api.depends('settlement_id', 'receipt_id')
    def _compute_is_third_party(self):
        for wiz in self:
            payer = wiz.settlement_id.partner_id
            insured = wiz.receipt_id.partner_id
            wiz.is_third_party = bool(payer and insured and payer != insured)

    def action_confirmer_imputation(self):
        self.ensure_one()
        if self.is_third_party and not self.confirm_third_party:
            raise UserError(_(
                'Le payeur (%(payer)s) diffère du client de la quittance '
                '(%(insured)s).\nCochez « Je confirme le paiement pour compte '
                'de tiers » pour continuer.',
                payer=self.settlement_id.partner_id.display_name,
                insured=self.receipt_id.partner_id.display_name,
            ))
        # EVO02 : une seule ligne par couple (règlement, quittance) —
        # si une imputation existe déjà, on FUSIONNE au lieu de créer
        # une seconde ligne (refusée par la contrainte anti-doublon).
        existing = self.env['insurance.settlement.imputation'].search([
            ('settlement_id', '=', self.settlement_id.id),
            ('receipt_id', '=', self.receipt_id.id),
            ('is_reconstructed', '=', False),
        ], limit=1)
        if existing:
            if self.montant_a_imputer <= 0:
                raise UserError(_('Le montant à imputer doit être positif.'))
            if self.montant_a_imputer > self.settlement_id.montant_restant + 0.001:
                raise UserError(_(
                    'Le montant à imputer (%(a).3f TND) dépasse le solde '
                    'disponible du règlement (%(b).3f TND).',
                    a=self.montant_a_imputer,
                    b=self.settlement_id.montant_restant,
                ))
            existing.write({
                'montant_impute': existing.montant_impute + self.montant_a_imputer,
                'date_imputation': self.date_imputation,
            })
            self.receipt_id._compute_amounts()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Imputation fusionnée'),
                    'message': _(
                        '%(montant).3f TND ajoutés à la ligne existante du '
                        'règlement %(reg)s (total : %(total).3f TND).',
                        montant=self.montant_a_imputer,
                        reg=self.settlement_id.name,
                        total=existing.montant_impute,
                    ),
                    'type': 'success',
                    'sticky': False,
                },
            }
        return super().action_confirmer_imputation()
