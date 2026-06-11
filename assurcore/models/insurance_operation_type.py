# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.operation.type — Référentiel des codes opérations
#  EVO02 — Migration depuis PR_CODE_OPERATION Oracle
#
#  Dans Oracle, chaque opération avait jusqu'à 4 codes (CODE_OPERATION1..4)
#  définissant précisément : la branche, le type d'acte, la variante et le détail.
#  Cette table permet de retrouver la désignation complète et le libellé honoraire.
#
#  Ex-table Oracle : PR_CODE_OPERATION
# ==============================================================================

from odoo import fields, models


class InsuranceOperationType(models.Model):
    """
    Référentiel des codes opérations Oracle.
    87 codes couvrant toutes les branches et types d'actes.
    """

    _name        = 'insurance.operation.type'
    _description = 'Type d\'Opération (Référentiel)'
    _order       = 'code_operation1, code_operation2'
    _rec_name    = 'code_label'

    # ── Codes à 4 niveaux (Oracle) ────────────────────────────────────────────

    code_operation1 = fields.Char(
        string='Code 1',
        size=10,
        required=True,
        index=True,
        help='Code principal. Ex-Oracle : CODE_OPERATION1.',
    )
    code_operation2 = fields.Char(
        string='Code 2',
        size=10,
        index=True,
        help='Sous-code. Ex-Oracle : CODE_OPERATION2.',
    )
    code_operation3 = fields.Char(
        string='Code 3',
        size=10,
        help='Variante. Ex-Oracle : CODE_OPERATION3.',
    )
    code_operation4 = fields.Char(
        string='Code 4',
        size=10,
        help='Détail. Ex-Oracle : CODE_OPERATION4.',
    )

    # ── Désignation et libellés ───────────────────────────────────────────────

    designation = fields.Char(
        string='Désignation',
        required=True,
        help='Libellé complet de l\'opération. Ex-Oracle : DESIGNATION.',
    )
    libelle_honoraire = fields.Char(
        string='Libellé Honoraire',
        size=100,
        help='Libellé à afficher sur la facture honoraires. '
             'Ex-Oracle : LIBELLE_HONORAIRE.',
    )
    description = fields.Text(
        string='Description',
        help='Description détaillée. Ex-Oracle : DESCRIPTION.',
    )

    # ── Classification ────────────────────────────────────────────────────────

    branche = fields.Char(
        string='Branche',
        size=50,
        index=True,
        help='Branche d\'assurance associée. Ex-Oracle : BRANCHE.',
    )
    risque = fields.Char(
        string='Risque',
        size=50,
        help='Type de risque couvert. Ex-Oracle : RISQUE.',
    )

    # ── Champ calculé affiché ─────────────────────────────────────────────────

    code_label = fields.Char(
        string='Référence',
        compute='_compute_code_label',
        store=True,
    )

    active = fields.Boolean(default=True)

    def _compute_code_label(self):
        for rec in self:
            codes = '/'.join(filter(None, [
                rec.code_operation1, rec.code_operation2,
                rec.code_operation3, rec.code_operation4,
            ]))
            rec.code_label = f'{codes} — {rec.designation}' if codes else rec.designation

    _sql_constraints = [
        ('code1_code2_uniq',
         'UNIQUE(code_operation1, code_operation2)',
         'Cette combinaison de codes existe déjà.'),
    ]
