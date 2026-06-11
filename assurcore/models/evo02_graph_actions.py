# -*- coding: utf-8 -*-
# EVO02 Lot 3 : boutons « Graphe » — ouvre le GraphExplorer avec l'objet en racine.
# NB : mixin en AbstractModel (le multi-héritage Python pur avec models.Model
# casse la reconstruction du registre Odoo : « object layout differs »).

from odoo import models, _

GRAPH_TYPE = {
    'insurance.operation': 'operation',
    'insurance.receipt': 'receipt',
    'insurance.settlement': 'settlement',
    'res.partner': 'partner',
}


class InsuranceGraphMixin(models.AbstractModel):
    _name = 'insurance.graph.mixin'
    _description = 'Ouverture du graphe de navigation AssurCore'

    def action_open_graph(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'assurcore_graph',
            'name': _('Graphe — %s') % self.display_name,
            'params': {
                'model': GRAPH_TYPE.get(self._name, 'operation'),
                'res_id': self.id,
            },
        }


class InsuranceOperationGraph(models.Model):
    _name = 'insurance.operation'
    _inherit = ['insurance.operation', 'insurance.graph.mixin']


class InsuranceReceiptGraph(models.Model):
    _name = 'insurance.receipt'
    _inherit = ['insurance.receipt', 'insurance.graph.mixin']


class InsuranceSettlementGraph(models.Model):
    _name = 'insurance.settlement'
    _inherit = ['insurance.settlement', 'insurance.graph.mixin']


class ResPartnerGraph(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'insurance.graph.mixin']
