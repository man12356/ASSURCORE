# -*- coding: utf-8 -*-
# EVO02 Lot 3 : boutons « Graphe » — ouvre le GraphExplorer avec l'objet en racine.

from odoo import models, _

GRAPH_TYPE = {
    'insurance.operation': 'operation',
    'insurance.receipt': 'receipt',
    'insurance.settlement': 'settlement',
    'res.partner': 'partner',
}


class GraphActionMixin:

    def action_open_graph(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'assurcore_graph',
            'name': _('Graphe — %s') % self.display_name,
            'params': {
                'model': GRAPH_TYPE[self._name],
                'res_id': self.id,
            },
        }


class InsuranceOperationGraph(models.Model, GraphActionMixin):
    _inherit = 'insurance.operation'


class InsuranceReceiptGraph(models.Model, GraphActionMixin):
    _inherit = 'insurance.receipt'


class InsuranceSettlementGraph(models.Model, GraphActionMixin):
    _inherit = 'insurance.settlement'


class ResPartnerGraph(models.Model, GraphActionMixin):
    _inherit = 'res.partner'
