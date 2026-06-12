#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — Correctif : import des SINISTRES (PR_SINISTRE), oublies par
#  evo02_full_etl.py qui les TRUNCATE en S0 sans les recharger.
#  Idempotent : DELETE des ORA-SIN-% puis re-insertion.
#  Execution : python3 evo02_import_sinistres.py  -> evo02_sinistres.sql
# ==============================================================================
import csv, io, os
from datetime import datetime

DATA = next((p for p in ('/mnt/extra-addons/DATA_REEL', 'DATA_REEL_22-05-2026/DATA_REEL') if os.path.isdir(p)), None)
OUT = '/mnt/extra-addons/evo02_sinistres.sql' if os.path.isdir('/mnt/extra-addons') else 'evo02_sinistres.sql'
BATCH = 500

def tsv(name):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        print('!! TSV manquant:', p); return []
    with io.open(p, encoding='utf-8', errors='replace') as f:
        return [{(k or '').strip().strip('"'): (v or '').strip().strip('"') for k, v in r.items()} for r in csv.DictReader(f, delimiter='\t')]

def S(v, maxlen=0):
    if v is None or str(v).strip() == '': return 'NULL'
    s = str(v)
    if maxlen: s = s[:maxlen]
    return "'" + s.replace("'", "''") + "'"

def N(v):
    s = (str(v or '')).replace(' ', '').replace(',', '.')
    try: return repr(float(s))
    except Exception: return '0'

def D(v, default='NULL'):
    s = (v or '').strip()
    for fmt in ('%d/%m/%y', '%d/%m/%Y'):
        try:
            d = datetime.strptime(s, fmt).date()
            if d.year < 1990: d = d.replace(year=d.year + 100)
            return "'" + d.isoformat() + "'"
        except Exception: pass
    return default

out = open(OUT, 'w', encoding='utf-8')
W = out.write
def values_block(prefix_sql, rows_sql):
    for i in range(0, len(rows_sql), BATCH):
        W(prefix_sql + ' VALUES\n' + ',\n'.join(rows_sql[i:i+BATCH]) + ';\n')

W("-- EVO02 SINISTRES — genere le %s\n" % datetime.now())
W("\\set ON_ERROR_STOP on\nBEGIN;\n")

# ── S8. Sinistres ─────────────────────────────────────────────────────────────
sin = tsv('PR_SINISTRE_DATA_TABLE.tsv')
TYPE_SIN = {'IDA': 'ida', 'Dommage_Collision': 'dommage_collision'}
W("""
-- S8. SINISTRES (PR_SINISTRE)
DELETE FROM insurance_claim WHERE name LIKE 'ORA-SIN-%';
DROP TABLE IF EXISTS tmp_sin;
CREATE TEMP TABLE tmp_sin (annee text, num text, num_pol text, dt date, lib text, cat text,
  montant numeric, hon numeric, hon_fact boolean, ref_sin text, tiers text, type_sin text,
  bdg numeric, vol numeric, total_paye numeric, compagnie text, supp boolean);
""")
rows = []
for r in sin:
    if not (r.get('NUM_SINISTRE') or '').strip(): continue
    rows.append('(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)' % (
        S(r.get('ANNEE_SIN'), 4), S(r.get('NUM_SINISTRE')), S(r.get('NUM_POLICE'), 30),
        D(r.get('DATE_SINISTRE'), "'2015-01-01'"), S(r.get('LIB_SINISTRE'), 250),
        S(r.get('CATEGORIE_INDEMNISATION'), 50), N(r.get('MONTANT_INDEMNITE')),
        N(r.get('MONTANT_HON_SIN_HT')), 'TRUE' if r.get('HON_SIN_FACTURE') == 'O' else 'FALSE',
        S(r.get('REF_SINISTRE'), 20), S(r.get('TIERS'), 50),
        S(TYPE_SIN.get((r.get('TYPE_SINISTRE') or '').strip())),
        N(r.get('BRIS_DE_GLACES')), N(r.get('VOL_INCENDIE')),
        N(r.get('TOTAL_INDEMNITE_PAYE')), S(r.get('COMPAGNIE'), 30),
        'TRUE' if r.get('SUPP_LOG') == 'O' else 'FALSE'))
values_block('INSERT INTO tmp_sin', rows)
W("""
INSERT INTO insurance_claim (name, state, policy_id, partner_id, company_ins_id, branche,
       commercial_id, agence_courtier, date_sinistre, date_declaration, lib_sinistre,
       categorie_indemnisation, tiers, ref_compagnie, type_sinistre, bris_de_glaces, vol_incendie,
       montant_reclame, montant_expertise, franchise, montant_indemnite, montant_indemnite_net,
       montant_honoraire_sin_ht, hon_sin_facture, currency_id, notes, supp_log, active,
       create_date, write_date, create_uid, write_uid)
SELECT 'ORA-SIN-'||t.annee||'-'||t.num, 'declare',
       p.id, p.partner_id, p.company_ins_id, p.branche, p.commercial_id, p.agence_courtier,
       t.dt::timestamp, t.dt, COALESCE(t.lib, 'Sinistre migre depuis Oracle -- '||t.num),
       t.cat, t.tiers, t.ref_sin, t.type_sin, t.bdg, t.vol,
       t.montant, 0, 0, t.montant, t.montant,
       t.hon, t.hon_fact, (SELECT id FROM res_currency WHERE name='TND'),
       'Migre depuis PR_SINISTRE '||t.annee||'/'||t.num||' | Compagnie: '||COALESCE(t.compagnie,'?')
        ||' | Total indemnite payee Oracle: '||COALESCE(t.total_paye,0)
        ||CASE WHEN p.num_police='FALLBACK-MIG' THEN ' | ANOMALIE: police Oracle introuvable ('||COALESCE(t.num_pol,'?')||')' ELSE '' END,
       t.supp, NOT t.supp, NOW(), NOW(), 1, 1
FROM tmp_sin t
JOIN insurance_policy p ON p.id = COALESCE(
     (SELECT id FROM insurance_policy ip WHERE ip.num_police = t.num_pol LIMIT 1),
     (SELECT id FROM insurance_policy ip WHERE ip.num_police = 'FALLBACK-MIG'));

SELECT 'sinistres' AS objet, count(*) FROM insurance_claim WHERE name LIKE 'ORA-SIN-%';
SELECT count(*) AS sinistres_police_fallback FROM insurance_claim c
JOIN insurance_policy p ON p.id=c.policy_id
WHERE c.name LIKE 'ORA-SIN-%' AND p.num_police='FALLBACK-MIG';
COMMIT;
""")
out.close()
print('S8 sinistres: %d lignes -> %s' % (len(rows), OUT))
