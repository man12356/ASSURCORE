# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class InsuranceBranch(models.Model):
    _name = 'insurance.branch'
    _description = 'Branche d\'Assurance'
    _order = 'sequence, name'

    name = fields.Char(string='Nom de la branche', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Description / Notes')

    _sql_constraints = [
        ('name_uniq', 'UNIQUE(name)', 'Ce nom de branche existe déjà.'),
        ('code_uniq', 'UNIQUE(code)', 'Ce code de branche existe déjà.'),
    ]
