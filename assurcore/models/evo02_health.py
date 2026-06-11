# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Lot 5 : Santé des données (second statut transversal)
#  Réf. : SPEC_Imputation_Operation_Graphe_Navigation.md (§2.5)
#
#  Principe : les anomalies (notamment celles migrées depuis Oracle) ne sont
#  jamais bloquées ni corrigées en silence. Chaque objet porte un second
#  statut « santé » (ok / anomalie) + le détail de chaque anomalie dans des
#  lignes insurance.anomaly, avec un workflow de résorption
#  (ouverte → justifiée / corrigée).
# ==============================================================================

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class InsuranceAnomalyType(models.Model):
    """Catalogue des types d'anomalies (initialisé depuis le rapport du
    11/06/2026 — voir data/evo02_anomaly_types.xml)."""

    _name = 'insurance.anomaly.type'
    _description = 'Type d\'anomalie de données'
    _order = 'severity desc, code'

    code = fields.Char(required=True, index=True)
    name = fields.Char(string='Libellé', required=True, translate=True)
    description = fields.Text(translate=True)
    severity = fields.Selection(
        [('info', 'Information'), ('warning', 'À surveiller'),
         ('error', 'Bloquante pour la comptabilité')],
        string='Sévérité', default='warning', required=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Le code du type d\'anomalie doit être unique.'),
    ]


class InsuranceAnomaly(models.Model):
    """Une anomalie constatée sur un objet (opération, quittance, règlement,
    imputation, client…)."""

    _name = 'insurance.anomaly'
    _description = 'Anomalie de données'
    _order = 'state, detected_date desc, id desc'
    _rec_name = 'display_label'

    # ── Objet porteur (référence générique) ────────────────────────────────────

    res_model = fields.Char(string='Modèle', required=True, index=True)
    res_id = fields.Many2oneReference(
        string='Enregistrement', model_field='res_model',
        required=True, index=True,
    )
    res_display = fields.Char(
        string='Objet', compute='_compute_res_display', store=False,
    )

    # ── Qualification ─────────────────────────────────────────────────────────

    type_id = fields.Many2one(
        'insurance.anomaly.type', string='Type', required=True, index=True,
    )
    severity = fields.Selection(related='type_id.severity', store=True)
    detail = fields.Text(
        string='Détail',
        help='Valeurs constatées : montants, écarts, références d\'origine '
             'Oracle… Ex : « lettré 9 917,650 pour un dû de 4 958,825 — '
             'règ. 10695 + 10712, aucun impayé saisi ».',
    )
    origin = fields.Selection(
        [('migration', 'Migration Oracle'), ('exploitation', 'Exploitation')],
        required=True, default='exploitation', index=True,
    )
    oracle_ref = fields.Char(
        string='Référence Oracle',
        help='Clé d\'origine dans l\'ancien système (NUM_OPERATION, '
             'NUM_REG_CLT, ANNEE/NUM_FACTURE…).',
    )

    # ── Traçabilité & workflow ─────────────────────────────────────────────────

    detected_date = fields.Datetime(default=fields.Datetime.now, required=True)
    detected_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user, readonly=True,
    )
    state = fields.Selection(
        [('ouverte', 'Ouverte'), ('justifiee', 'Justifiée'),
         ('corrigee', 'Corrigée')],
        default='ouverte', required=True, index=True, tracking=False,
    )
    resolution_note = fields.Text(string='Justification / correction')
    resolved_by = fields.Many2one('res.users', readonly=True)
    resolved_date = fields.Datetime(readonly=True)

    display_label = fields.Char(compute='_compute_res_display')

    # ── Calculs ────────────────────────────────────────────────────────────────

    def _compute_res_display(self):
        for rec in self:
            target = None
            if rec.res_model in self.env and rec.res_id:
                target = self.env[rec.res_model].browse(rec.res_id).exists()
            rec.res_display = target.display_name if target else (
                f'{rec.res_model},{rec.res_id}')
            rec.display_label = f'[{rec.type_id.code}] {rec.res_display}'

    # ── Workflow de résorption ─────────────────────────────────────────────────

    def action_justify(self):
        for rec in self:
            if not rec.resolution_note:
                raise UserError(_(
                    'Une justification écrite est obligatoire pour clore '
                    'une anomalie sans la corriger.'))
            rec.write({
                'state': 'justifiee',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
            })
        self._refresh_targets()

    def action_mark_corrected(self):
        for rec in self:
            rec.write({
                'state': 'corrigee',
                'resolved_by': self.env.user.id,
                'resolved_date': fields.Datetime.now(),
            })
        self._refresh_targets()

    def action_reopen(self):
        self.write({'state': 'ouverte', 'resolved_by': False,
                    'resolved_date': False})
        self._refresh_targets()

    def action_open_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Synchronisation du statut santé des objets porteurs ───────────────────

    def _refresh_targets(self):
        """Recalcule health_state des objets porteurs concernés."""
        for (model, ids) in self._group_targets().items():
            if model in self.env and hasattr(self.env[model], '_compute_health_state'):
                records = self.env[model].browse(ids).exists()
                records._compute_health_state()

    def _group_targets(self):
        grouped = {}
        for rec in self:
            grouped.setdefault(rec.res_model, set()).add(rec.res_id)
        return {m: list(v) for m, v in grouped.items()}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_targets()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals or 'res_id' in vals or 'res_model' in vals:
            self._refresh_targets()
        return res

    def unlink(self):
        targets = self._group_targets()
        res = super().unlink()
        for model, ids in targets.items():
            if model in self.env and hasattr(self.env[model], '_compute_health_state'):
                self.env[model].browse(ids).exists()._compute_health_state()
        return res


class InsuranceHealthMixin(models.AbstractModel):
    """Mixin à hériter par tout modèle devant porter le second statut santé."""

    _name = 'insurance.health.mixin'
    _description = 'Santé des données (anomalies)'

    health_state = fields.Selection(
        [('ok', 'Saine'), ('anomalie', 'Avec anomalie')],
        string='Santé', default='ok', index=True, copy=False, readonly=True,
        help='Second statut : présence d\'anomalies de données ouvertes '
             'sur cet enregistrement.',
    )
    anomaly_ids = fields.One2many(
        'insurance.anomaly', compute='_compute_anomaly_ids',
        string='Anomalies',
    )
    anomaly_count = fields.Integer(compute='_compute_anomaly_ids')
    anomaly_note = fields.Text(
        string='Note d\'anomalie', compute='_compute_anomaly_ids',
        help='Détail lisible des anomalies ouvertes (affiché en bandeau).',
    )

    def _compute_anomaly_ids(self):
        Anomaly = self.env['insurance.anomaly']
        for rec in self:
            lines = Anomaly.search([
                ('res_model', '=', rec._name), ('res_id', '=', rec.id),
            ])
            rec.anomaly_ids = lines
            open_lines = lines.filtered(lambda l: l.state == 'ouverte')
            rec.anomaly_count = len(open_lines)
            rec.anomaly_note = '\n'.join(
                f'• [{l.type_id.code}] {l.type_id.name}'
                + (f' — {l.detail}' if l.detail else '')
                for l in open_lines
            ) or False

    def _compute_health_state(self):
        """Appelée par insurance.anomaly à chaque changement."""
        Anomaly = self.env['insurance.anomaly']
        for rec in self:
            nb_open = Anomaly.search_count([
                ('res_model', '=', rec._name), ('res_id', '=', rec.id),
                ('state', '=', 'ouverte'),
            ])
            new_state = 'anomalie' if nb_open else 'ok'
            if rec.health_state != new_state:
                rec.sudo().write({'health_state': new_state})

    def action_view_anomalies(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Anomalies — %s') % self.display_name,
            'res_model': 'insurance.anomaly',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }

    def add_anomaly(self, type_code, detail=False, origin='exploitation',
                    oracle_ref=False):
        """Helper : crée une anomalie sur self (utilisé par la migration
        et les contrôles applicatifs)."""
        atype = self.env['insurance.anomaly.type'].search(
            [('code', '=', type_code)], limit=1)
        if not atype:
            raise ValidationError(_('Type d\'anomalie inconnu : %s') % type_code)
        return self.env['insurance.anomaly'].create([{
            'res_model': rec._name,
            'res_id': rec.id,
            'type_id': atype.id,
            'detail': detail,
            'origin': origin,
            'oracle_ref': oracle_ref,
        } for rec in self])


# ── Application du mixin aux modèles métier ───────────────────────────────────

class InsuranceOperationHealth(models.Model):
    _name = 'insurance.operation'
    _inherit = ['insurance.operation', 'insurance.health.mixin']


class InsuranceReceiptHealth(models.Model):
    _name = 'insurance.receipt'
    _inherit = ['insurance.receipt', 'insurance.health.mixin']


class InsuranceSettlementHealth(models.Model):
    _name = 'insurance.settlement'
    _inherit = ['insurance.settlement', 'insurance.health.mixin']


class InsuranceSettlementImputationHealth(models.Model):
    _name = 'insurance.settlement.imputation'
    _inherit = ['insurance.settlement.imputation', 'insurance.health.mixin']


class ResPartnerHealth(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'insurance.health.mixin']
