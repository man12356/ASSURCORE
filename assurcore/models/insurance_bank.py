# -*- coding: utf-8 -*-
# ==============================================================================
#  insurance.bank — Référentiel des Banques tunisiennes
#  insurance.journal.enc — Journée d'Encaissement Compagnie
#
#  Ex-table Oracle : PR_BANQUE, PR_JOUR_ENC
# ==============================================================================

from odoo import api, fields, models, _


class InsuranceBank(models.Model):
    """
    Référentiel des banques (tireurs de chèques).
    Utilisé dans insurance.settlement pour identifier la banque du payeur.
    Équivalent Oracle : PR_BANQUE (table BANQUE VARCHAR2(100)).
    """

    _name        = 'insurance.bank'
    _description = 'Banque (Référentiel)'
    _order       = 'name asc'
    _rec_name    = 'name'

    name = fields.Char(
        string='Nom de la banque',
        required=True,
        size=100,
        help='Ex: BH, STB, BIAT, Attijari, UIB, Zitouna… '
             'Ex-champ Oracle : BANQUE VARCHAR2(100) dans PR_BANQUE.',
    )

    code_swift = fields.Char(
        string='Code SWIFT/BIC',
        size=11,
        help='Code international de la banque (optionnel).',
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Ce nom de banque existe déjà.'),
    ]
