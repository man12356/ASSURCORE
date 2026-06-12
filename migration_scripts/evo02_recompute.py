# -*- coding: utf-8 -*-
# EVO02 — Recalcul des champs calcules stockes apres import SQL direct
# (odoo shell) : ident_mode + settlement_state sur toutes les operations.
print('Recalcul ident_mode + settlement_state...')
Op = env['insurance.operation'].with_context(active_test=False)
ops = Op.search([])
print('Operations : %d' % len(ops))
BATCH = 2000
for i in range(0, len(ops), BATCH):
    chunk = ops[i:i + BATCH]
    chunk._compute_ident_mode()
    chunk._compute_settlement_state()
    env.cr.commit()
    print('  %d / %d' % (min(i + BATCH, len(ops)), len(ops)))
gen = ops.filtered(lambda o: o.ident_mode == 'cle_metier')
print('ident_mode=cle_metier (quittances generiques) : %d' % len(gen))
states = {}
for o in ops:
    states[o.settlement_state] = states.get(o.settlement_state, 0) + 1
print('settlement_state :', states)
env.cr.commit()
print('RECALCUL TERMINE')
