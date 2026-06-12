# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — LOT 4 : Migration de l'historique vers la granularité EVO02
#  Réf. : SPEC_Imputation_Operation_Graphe_Navigation.md §3 + PLAN T6.x
#
#  Ce script s'exécute DANS odoo shell (l'objet `env` est fourni) :
#
#    1. Copier les TSV dans le volume visible du conteneur :
#         Copy-Item -Recurse .\DATA_REEL_22-05-2026\DATA_REEL .\data_db\DATA_REEL -Force
#    2. Lancer :
#         Get-Content .\migration_scripts\evo02_lot4_migration.py |
#           docker compose run --rm -T web odoo shell -c /etc/odoo/odoo.conf -d assurcore_db
#
#  Étapes :
#    A. Backfill internal_ref sur les opérations migrées (T6.3)
#    B. Flag is_reconstructed sur les imputations issues de la migration (T6.1)
#    C. Ventilation FIFO : imputations des mémoires multi-opérations
#       éclatées par opération, par date d'opération croissante (T6.1)
#    D. Création des anomalies du rapport du 11/06/2026 (T6.2)
#    E. Recette chiffrée : comparaison aux comptages du rapport (T6.4)
#
#  Idempotent : ré-exécutable sans doublons (anomalies dédupliquées par
#  type+oracle_ref, FIFO non rejoué si déjà ventilé, refs non régénérées).
# ==============================================================================

import csv
import io
import os
from datetime import datetime, date

# ── PARAMÈTRES (arbitrages phase 0 — à ajuster si le client tranche autrement) ─
# TSV Oracle : /mnt/extra-addons = ./addons (monté sur le conteneur web)
_CANDIDATS = ['/mnt/extra-addons/DATA_REEL', '/backups/DATA_REEL']
DATA_DIR = next((p for p in _CANDIDATS if os.path.isdir(p)), _CANDIDATS[0])
DRY_RUN = False                      # True = tout calculer, ne rien écrire
SEUIL_OP_NON_FACTUREE = date(2025, 6, 1)   # T0.2 : avant cette date = anomalie
CREER_ANOMALIES_QUITTANCE_GENERIQUE = True  # T0.3
PRECISION = 0.005

LOG = []
def log(msg):
    print(msg)
    LOG.append(str(msg))

# ── Lecture TSV ────────────────────────────────────────────────────────────────
def read_tsv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        log('  !! TSV introuvable : %s' % path)
        return []
    with io.open(path, encoding='utf-8', errors='replace') as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    return [{(k or '').strip().strip('"'): (v or '').strip().strip('"')
             for k, v in r.items()} for r in rows]

def fnum(s):
    s = (s or '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

log('=' * 70)
log('EVO02 LOT 4 — démarrage %s (DRY_RUN=%s)' % (datetime.now(), DRY_RUN))
log('=' * 70)

ops_tsv = read_tsv('PR_OPERATION_DATA_TABLE.tsv')
fact_tsv = read_tsv('PR_FACTURE_DATA_TABLE.tsv')
reg_tsv = read_tsv('PR_REGELEMENT_DATA_TABLE.tsv')
rf_tsv = read_tsv('PR_REG_FACTURE_DATA_TABLE.tsv')
log('TSV charges : ops=%d fact=%d reg=%d lettrage=%d'
    % (len(ops_tsv), len(fact_tsv), len(reg_tsv), len(rf_tsv)))

# ── Index Odoo (une seule requête par modèle) ─────────────────────────────────
Operation = env['insurance.operation'].with_context(active_test=False)
Receipt = env['insurance.receipt'].with_context(active_test=False)
Settlement = env['insurance.settlement'].with_context(active_test=False)
Imputation = env['insurance.settlement.imputation'].with_context(
    evo02_skip_checks=True)
Anomaly = env['insurance.anomaly']
AnomalyType = env['insurance.anomaly.type']

def index_by_name(model, prefix):
    recs = model.search([('name', 'like', prefix + '%')])
    return {r.name: r for r in recs}, recs

op_idx, all_ops = index_by_name(Operation, 'ORA-OP-')
rcpt_idx, all_rcpts = index_by_name(Receipt, 'ORA-FACT-')
sett_idx, all_setts = index_by_name(Settlement, 'ORA-REG-')
log('Odoo : operations migrees=%d quittances/memoires=%d reglements=%d'
    % (len(op_idx), len(rcpt_idx), len(sett_idx)))

atype_idx = {t.code: t.id for t in AnomalyType.search([])}
existing_keys = set()
for a in Anomaly.search_read(
        [('origin', '=', 'migration')], ['type_id', 'oracle_ref']):
    existing_keys.add((a['type_id'][0], a['oracle_ref'] or ''))

stats = {}
anomaly_vals = []   # REX projet : creations par LOTS (model_create_multi),
                    # pas une par une — ~10x plus rapide via l'ORM in-process.
def add_anomaly(record, code, detail, oracle_ref):
    stats[code] = stats.get(code, 0) + 1
    if DRY_RUN or not record:
        return
    tid = atype_idx.get(code)
    if not tid:
        log('  !! type anomalie inconnu %s' % code)
        return
    if (tid, oracle_ref or '') in existing_keys:
        return  # idempotence
    existing_keys.add((tid, oracle_ref or ''))
    anomaly_vals.append({
        'res_model': record._name, 'res_id': record.id,
        'type_id': tid, 'detail': detail,
        'origin': 'migration', 'oracle_ref': oracle_ref,
    })

def flush_anomalies():
    if not anomaly_vals:
        return
    BATCH = 2000
    for i in range(0, len(anomaly_vals), BATCH):
        Anomaly.create(anomaly_vals[i:i + BATCH])
    log('  -> %d anomalies creees (par lots de %d)' % (len(anomaly_vals), BATCH))
    anomaly_vals.clear()

# ══════════════════════════════════════════════════════════════════════════════
log('\nA. Backfill internal_ref + recalcul ident_mode')
# ══════════════════════════════════════════════════════════════════════════════
# REX projet : SQL direct (pas de logique metier sur ce champ) — instantane
# au lieu de 2 requetes x 24 000 operations via la sequence ORM.
env.cr.execute("SELECT count(*) FROM insurance_operation "
               "WHERE internal_ref IS NULL")
nb_sans_ref = env.cr.fetchone()[0]
log('  operations sans reference interne : %d' % nb_sans_ref)
if not DRY_RUN and nb_sans_ref:
    env.cr.execute("""
        UPDATE insurance_operation
           SET internal_ref = 'OP-MIG-' || lpad(id::text, 7, '0')
         WHERE internal_ref IS NULL
    """)
    all_ops.invalidate_recordset(['internal_ref'])
    log('  -> references generees en un seul UPDATE (prefixe OP-MIG-)')

# ══════════════════════════════════════════════════════════════════════════════
log('\nB. Flag is_reconstructed sur les imputations migrees')
# ══════════════════════════════════════════════════════════════════════════════
mig_lines = Imputation.search([
    ('settlement_id', 'in', all_setts.ids),
    ('is_reconstructed', '=', False),
])
log('  lignes de lettrage migrees a flaguer : %d' % len(mig_lines))
if not DRY_RUN and mig_lines:
    env.cr.execute(
        'UPDATE insurance_settlement_imputation SET is_reconstructed = TRUE '
        'WHERE id IN %s', (tuple(mig_lines.ids),))
    mig_lines.invalidate_recordset()
    log('  -> flaguees')

# ══════════════════════════════════════════════════════════════════════════════
log('\nC. Ventilation FIFO des memoires multi-operations')
# ══════════════════════════════════════════════════════════════════════════════
# Pour chaque imputation migree dont la quittance/memoire regroupe plusieurs
# operations : on eclate la ligne en N lignes (une par operation, FIFO date_op),
# plafonnees au du de chaque operation. Regle T0.1 (defaut valide a confirmer).
def op_due(op):
    return (op.montant_prime or 0.0) + (op.montant_honoraire_ht or 0.0) \
        + (op.montant_tva or 0.0)

multi = [r for r in all_rcpts if len(r.operation_ids) > 1]
log('  memoires multi-operations : %d' % len(multi))
nb_split, nb_lines_new = 0, 0
fifo_vals = []   # REX projet : creation par lots en fin de boucle
for rcpt in multi:
    ops_sorted = rcpt.operation_ids.sorted(
        key=lambda o: (o.date_op or date(1900, 1, 1), o.id))
    lines = Imputation.search([
        ('receipt_id', '=', rcpt.id),
        ('is_reconstructed', '=', True),
    ], order='date_imputation, id')
    # deja ventile ? (plus d'une ligne par reglement ou operation_id varie)
    if not lines or all(
            l.operation_id and len(lines.filtered(
                lambda x: x.settlement_id == l.settlement_id)) > 1
            for l in lines):
        continue
    # restant du par operation (FIFO global sur la memoire)
    remaining = {o.id: op_due(o) for o in ops_sorted}
    for line in lines:
        amount = line.montant_impute
        chunks = []
        for o in ops_sorted:
            if amount <= PRECISION:
                break
            take = min(amount, max(remaining[o.id], 0.0))
            if take > PRECISION:
                chunks.append((o, take))
                remaining[o.id] -= take
                amount -= take
        if amount > PRECISION and chunks:
            # excedent (memoire sur-reglee) : laisse sur la derniere operation
            chunks[-1] = (chunks[-1][0], chunks[-1][1] + amount)
        if not chunks:
            chunks = [(ops_sorted[0], line.montant_impute)]
        nb_split += 1
        if DRY_RUN:
            continue
        first_op, first_amount = chunks[0]
        line.write({'operation_id': first_op.id,
                    'montant_impute': first_amount})
        for (o, amt) in chunks[1:]:
            fifo_vals.append({
                'settlement_id': line.settlement_id.id,
                'receipt_id': rcpt.id,
                'operation_id': o.id,
                'montant_impute': amt,
                'date_imputation': line.date_imputation,
                'is_reconstructed': True,
                'notes': 'Ventilation FIFO EVO02 depuis %s' % line.name,
            })
            nb_lines_new += 1
if not DRY_RUN and fifo_vals:
    BATCH = 2000
    for i in range(0, len(fifo_vals), BATCH):
        Imputation.create(fifo_vals[i:i + BATCH])
log('  lignes ventilees : %d (nouvelles lignes creees : %d, par lots)'
    % (nb_split, nb_lines_new))

# ══════════════════════════════════════════════════════════════════════════════
log('\nD. Creation des anomalies (rapport du 11/06/2026)')
# ══════════════════════════════════════════════════════════════════════════════
def k(s):
    return (s or '').strip()

fact_keys = {(k(f['ANNEE_FACT']), k(f['NUM_FACTURE'])) for f in fact_tsv}
reg_keys = {k(r['NUM_REG_CLT']) for r in reg_tsv}

# D1 — operations referencant une memoire inexistante (123)
for o in ops_tsv:
    nf, an = k(o.get('NUM_FACTURE_PRIME')), k(o.get('ANNEE_FACT_PRIME'))
    if nf and nf != '0' and (an, nf) not in fact_keys:
        rec = op_idx.get('ORA-OP-' + k(o['NUM_OPERATION']))
        add_anomaly(rec, 'MEM_INEXISTANTE',
                    'Reference Oracle %s/%s absente de PR_FACTURE' % (an, nf),
                    'OP-%s->FACT-%s/%s' % (k(o['NUM_OPERATION']), an, nf))

# D2 — memoires sans aucune operation (316) + D6 TOTAL_REG incoherent (253)
ops_by_fact = {}
for o in ops_tsv:
    nf, an = k(o.get('NUM_FACTURE_PRIME')), k(o.get('ANNEE_FACT_PRIME'))
    if nf:
        ops_by_fact.setdefault((an, nf), []).append(o)
lettrage_by_fact = {}
for r in rf_tsv:
    kk = (k(r['ANNEE_FACT']), k(r['NUM_FACTURE']))
    lettrage_by_fact[kk] = lettrage_by_fact.get(kk, 0.0) + fnum(r['MONTANT_REG'])
for f in fact_tsv:
    kk = (k(f['ANNEE_FACT']), k(f['NUM_FACTURE']))
    rec = rcpt_idx.get('ORA-FACT-%s-%s' % kk)
    if kk not in ops_by_fact:
        add_anomaly(rec, 'MEM_ORPHELINE',
                    'Memoire sans operation rattachee — TOTAL_FACT=%s' %
                    f.get('TOTAL_FACT'), 'FACT-%s/%s' % kk)
    lettre = lettrage_by_fact.get(kk, 0.0)
    tf, tr = fnum(f.get('TOTAL_FACT')), fnum(f.get('TOTAL_REG'))
    if abs(tr - lettre) > PRECISION:
        add_anomaly(rec, 'TOTAL_REG_INCOHERENT',
                    'TOTAL_REG Oracle=%.3f vs lettrage reel=%.3f (ecart %.3f)'
                    % (tr, lettre, tr - lettre), 'TR-%s/%s' % kk)
    if lettre > tf + PRECISION:
        add_anomaly(rec, 'SUR_REGLEMENT',
                    'Lettre %.3f pour un du de %.3f (ecart %.3f)'
                    % (lettre, tf, lettre - tf), 'SR-%s/%s' % kk)

# D3 — reglements sur-imputes (3) + lettrages orphelins (95+28)
alloc_by_reg = {}
for r in rf_tsv:
    nr = k(r['NUM_REG_CLT'])
    alloc_by_reg[nr] = alloc_by_reg.get(nr, 0.0) + fnum(r['MONTANT_REG'])
    kk = (k(r['ANNEE_FACT']), k(r['NUM_FACTURE']))
    if kk not in fact_keys:
        add_anomaly(sett_idx.get('ORA-REG-' + nr), 'LETTRAGE_ORPHELIN',
                    'Lettrage de %.3f vers memoire inexistante %s/%s'
                    % (fnum(r['MONTANT_REG']), kk[0], kk[1]),
                    'LO-FACT-%s-%s/%s' % (nr, kk[0], kk[1]))
    if nr not in reg_keys:
        rec = rcpt_idx.get('ORA-FACT-%s-%s' % kk)
        add_anomaly(rec, 'LETTRAGE_ORPHELIN',
                    'Lettrage de %.3f depuis reglement inexistant %s'
                    % (fnum(r['MONTANT_REG']), nr),
                    'LO-REG-%s-%s/%s' % (nr, kk[0], kk[1]))
for r in reg_tsv:
    nr = k(r['NUM_REG_CLT'])
    montant, alloue = fnum(r.get('MONTANT_REG')), alloc_by_reg.get(nr, 0.0)
    if alloue > montant + PRECISION:
        add_anomaly(sett_idx.get('ORA-REG-' + nr), 'SUR_IMPUTATION',
                    'Impute %.3f pour un reglement de %.3f (ecart %.3f)'
                    % (alloue, montant, alloue - montant), 'SI-' + nr)

# D4 — operations anciennes jamais facturees (parametre SEUIL)
for o in ops_tsv:
    if k(o.get('NUM_FACTURE_PRIME')):
        continue
    try:
        d = datetime.strptime(k(o.get('DATE_OP')), '%d/%m/%y').date()
        if d.year < 2000:
            d = d.replace(year=d.year + 100)
    except Exception:
        continue
    if d < SEUIL_OP_NON_FACTUREE:
        rec = op_idx.get('ORA-OP-' + k(o['NUM_OPERATION']))
        add_anomaly(rec, 'OP_NON_FACTUREE_ANCIENNE',
                    'Operation du %s jamais facturee (prime %s)'
                    % (k(o.get('DATE_OP')), o.get('MONTANT_PRIME')),
                    'ONF-' + k(o['NUM_OPERATION']))

# D5 — quittances generiques (toutes compagnies)
if CREER_ANOMALIES_QUITTANCE_GENERIQUE:
    matcher = env['insurance.receipt.matcher']
    generiques = all_ops.filtered(
        lambda op: not matcher.is_identifier_usable(
            op.num_quittance, op.num_police))
    log('  operations a quittance generique : %d' % len(generiques))
    for op in generiques:
        add_anomaly(op, 'QUITTANCE_GENERIQUE',
                    'Valeur d\'origine : "%s" (compagnie %s) — identification '
                    'par cle metier' % (op.num_quittance or '',
                                        op.company_ins_id.name or ''),
                    'QG-' + op.name)

# ══════════════════════════════════════════════════════════════════════════════
log('\nE. RECETTE — comptages vs rapport du 11/06/2026')
# ==============================================================================
attendus = {'MEM_INEXISTANTE': 123, 'MEM_ORPHELINE': 316, 'SUR_IMPUTATION': 3,
            'SUR_REGLEMENT': 29, 'LETTRAGE_ORPHELIN': 95 + 28,
            'TOTAL_REG_INCOHERENT': 253}
ok = True
for code, att in attendus.items():
    got = stats.get(code, 0)
    verdict = 'OK' if got == att else '!! ECART'
    if got != att:
        ok = False
    log('  %-22s attendu=%-5d obtenu=%-5d %s' % (code, att, got, verdict))
for code in ('OP_NON_FACTUREE_ANCIENNE', 'QUITTANCE_GENERIQUE'):
    log('  %-22s obtenu=%d (parametrique, pas de comptage de reference)'
        % (code, stats.get(code, 0)))

if DRY_RUN:
    log('\nDRY_RUN : aucune ecriture. Relancer avec DRY_RUN=False pour appliquer.')
    env.cr.rollback()
else:
    flush_anomalies()
    env.cr.commit()
    log('\nCOMMIT effectue.')
log('FIN — %s' % ('RECETTE CONFORME' if ok else 'ECARTS A ANALYSER (voir ci-dessus)'))
