# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Lot 3 : API du graphe de navigation
#  Réf. : SPEC_Imputation_Operation_Graphe_Navigation.md (§4)
#
#  Règles serveur :
#    RG-1  exclusion de type : aucun nœud du même type que la racine
#    RG-2  arêtes 'allocation' (avec montant) et 'structure' (pointillé)
#    RG-3  pagination par niveau/type (limit_per_level, défaut 25)
#    RG-4  droits : les enregistrements non autorisés sont omis
#    RG-5  profondeur max 4
# ==============================================================================

from odoo import http, _
from odoo.http import request

TYPES = {
    'insurance.operation': 'operation',
    'insurance.receipt': 'receipt',
    'insurance.settlement': 'settlement',
    'res.partner': 'partner',
}
MODELS = {v: k for k, v in TYPES.items()}
MAX_DEPTH = 4


class AssurcoreGraphController(http.Controller):

    @http.route('/assurcore/graph/node', type='json', auth='user')
    def graph_node(self, model=None, res_id=None, limit_per_level=25, **kw):
        if not model or model not in MODELS or not res_id:
            return {'error': _(
                'Contexte du graphe perdu (retour navigateur). '
                'Rouvrez le graphe depuis la fiche d\'un enregistrement '
                'via le bouton « Graphe ».')}
        record = request.env[MODELS[model]].browse(int(res_id))
        if not record.exists() or not self._readable(record):
            return {'error': _('Enregistrement introuvable ou non autorisé.')}

        root_key = f'{model}:{record.id}'
        nodes, edges = {}, []
        truncated = {}
        nodes[root_key] = self._node_payload(model, record, is_root=True)

        visited = {root_key}
        frontier = [(model, record)]
        depth = 0
        while frontier and depth < MAX_DEPTH:
            depth += 1
            next_frontier = []
            for (ntype, rec) in frontier:
                for (tgt_type, tgt_rec, kind, edge_data) in self._neighbors(
                        ntype, rec, limit_per_level, truncated):
                    # RG-1 : jamais de nœud du type de la racine
                    if tgt_type == model:
                        continue
                    if not self._readable(tgt_rec):
                        continue  # RG-4
                    key = f'{tgt_type}:{tgt_rec.id}'
                    if key not in visited:
                        visited.add(key)
                        nodes[key] = self._node_payload(tgt_type, tgt_rec)
                        next_frontier.append((tgt_type, tgt_rec))
                    edge = {
                        'from': f'{ntype}:{rec.id}', 'to': key, 'kind': kind,
                    }
                    edge.update(edge_data or {})
                    if not self._edge_exists(edges, edge):
                        edges.append(edge)
            frontier = next_frontier

        return {
            'root': {'key': root_key},
            'nodes': list(nodes.values()),
            'edges': edges,
            'truncated': truncated,
        }

    # ── Voisinage par type ─────────────────────────────────────────────────────

    def _neighbors(self, ntype, rec, limit, truncated):
        """Retourne [(type, record, kind, edge_data)]."""
        out = []
        if ntype == 'operation':
            if rec.receipt_id:
                out.append(('receipt', rec.receipt_id, 'structure', None))
            for line in rec.allocation_ids:
                if line.settlement_id:
                    out.append(('settlement', line.settlement_id, 'allocation', {
                        'amount': round(line.montant_impute, 3),
                        'reconstructed': line.is_reconstructed,
                        'third_party': line.is_third_party,
                    }))
        elif ntype == 'receipt':
            ops = rec.operation_ids
            for op in self._page(ops, limit, truncated, 'operation'):
                out.append(('operation', op, 'structure', None))
            if rec.partner_id:
                out.append(('partner', rec.partner_id, 'structure', None))
            for line in rec.imputation_ids:
                if line.settlement_id and not line.operation_id:
                    # lettrage de niveau quittance (pas de detail operation)
                    out.append(('settlement', line.settlement_id, 'allocation', {
                        'amount': round(line.montant_impute, 3),
                        'reconstructed': line.is_reconstructed,
                        'third_party': line.is_third_party,
                    }))
        elif ntype == 'settlement':
            if rec.partner_id:
                out.append(('partner', rec.partner_id, 'structure', None))
            lines = rec.imputation_ids
            for line in self._page(lines, limit, truncated, 'imputation'):
                if line.operation_id:
                    out.append(('operation', line.operation_id, 'allocation', {
                        'amount': round(line.montant_impute, 3),
                        'reconstructed': line.is_reconstructed,
                        'third_party': line.is_third_party,
                    }))
                elif line.receipt_id:
                    out.append(('receipt', line.receipt_id, 'allocation', {
                        'amount': round(line.montant_impute, 3),
                        'reconstructed': line.is_reconstructed,
                        'third_party': line.is_third_party,
                    }))
        elif ntype == 'partner':
            Settlement = request.env['insurance.settlement']
            Receipt = request.env['insurance.receipt']
            setts = Settlement.search(
                [('partner_id', '=', rec.id)],
                order='date_reg desc', limit=limit + 1)
            for s in self._page(setts, limit, truncated, 'settlement'):
                out.append(('settlement', s, 'structure', None))
            rcpts = Receipt.search(
                [('partner_id', '=', rec.id)],
                order='date_emission desc', limit=limit + 1)
            for r in self._page(rcpts, limit, truncated, 'receipt'):
                out.append(('receipt', r, 'structure', None))
        return out

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _page(self, records, limit, truncated, label):
        if len(records) > limit:
            truncated[label] = {
                'truncated': True, 'remaining': len(records) - limit}
            return records[:limit]
        return records

    @staticmethod
    def _edge_exists(edges, edge):
        return any(
            e['from'] == edge['from'] and e['to'] == edge['to']
            and e['kind'] == edge['kind'] for e in edges)

    @staticmethod
    def _readable(rec):
        try:
            rec.check_access_rights('read')
            rec.check_access_rule('read')
            return True
        except Exception:
            return False

    def _node_payload(self, ntype, rec, is_root=False):
        fmt = lambda v: f'{(v or 0.0):,.3f}'.replace(',', ' ')
        payload = {
            'key': f'{ntype}:{rec.id}',
            'type': ntype,
            'label': rec.display_name,
            'is_root': is_root,
            'health': getattr(rec, 'health_state', 'ok') or 'ok',
            'action': {'res_model': rec._name, 'res_id': rec.id},
            'subtitle': '',
            'tooltip': {},
        }
        if ntype == 'operation':
            payload['subtitle'] = fmt(rec.montant_prime) + ' TND'
            payload['state'] = rec.settlement_state
            payload['tooltip'] = {
                _('Quittance compagnie'): rec.num_quittance or _('(générique)'),
                _('Compagnie'): rec.company_ins_id.name or '',
                _('Police'): rec.num_police or '',
                _('Date'): str(rec.date_op or ''),
                _('Prime'): fmt(rec.montant_prime),
                _('Réglé'): fmt(rec.amount_paid_op),
                _('Reste'): fmt(rec.amount_residual_op),
                _('Réf. interne'): rec.internal_ref or '',
                _('Santé'): dict(rec._fields['health_state'].selection).get(
                    rec.health_state, ''),
            }
        elif ntype == 'receipt':
            payload['subtitle'] = '%s · %s %s' % (
                fmt(rec.amount_total), _('réglé'), fmt(rec.amount_paid))
            payload['tooltip'] = {
                _('État'): dict(rec._fields['state'].selection).get(rec.state, ''),
                _('Client'): rec.partner_id.display_name or '',
                _('Émission'): str(rec.date_emission or ''),
                _('Total dû'): fmt(rec.amount_total),
                _('Encaissé'): fmt(rec.amount_paid),
                _('Reste'): fmt(rec.amount_residual),
            }
        elif ntype == 'settlement':
            payload['subtitle'] = '%s · %s %s' % (
                fmt(rec.montant_reg), _('imputé'), fmt(rec.montant_impute_total))
            payload['tooltip'] = {
                _('Mode'): dict(rec._fields['type_reg'].selection).get(
                    rec.type_reg, ''),
                _('Date'): str(rec.date_reg or ''),
                _('Payeur'): rec.partner_id.display_name or '',
                _('Montant'): fmt(rec.montant_reg),
                _('Imputé'): fmt(rec.montant_impute_total),
                _('État'): dict(rec._fields['state'].selection).get(rec.state, ''),
            }
        elif ntype == 'partner':
            payload['subtitle'] = _('client')
            payload['tooltip'] = {
                _('Nom'): rec.display_name,
                _('Téléphone'): rec.phone or '',
                _('Ville'): rec.city or '',
            }
        return payload
