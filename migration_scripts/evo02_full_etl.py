#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
#  EVO02 — RE-IMPORT COMPLET (SQL direct, REX projet)
#  Genere evo02_full_import.sql : reset metier (config/users preserves)
#  + clients + polices + quittances + operations + reglements + lettrage.
#  Execution : python3 evo02_full_etl.py  (dans le conteneur web)
#    lit  /mnt/extra-addons/DATA_REEL/*.tsv
#    ecrit /mnt/extra-addons/evo02_full_import.sql
# ==============================================================================
import csv, io, os
from datetime import datetime

DATA = next((p for p in ('/mnt/extra-addons/DATA_REEL', 'DATA_REEL_22-05-2026/DATA_REEL') if os.path.isdir(p)), None)
OUT = '/mnt/extra-addons/evo02_full_import.sql' if os.path.isdir('/mnt/extra-addons') else 'evo02_full_import.sql'
BATCH = 500

BRANCHE_MAP = {'AUTO':'AUTO','AUTOMOBILE':'AUTO','VEH':'AUTO','MALADIE':'SANTE','SANTE':'SANTE','SANTÉ':'SANTE','MRH':'MRH','HABITATION':'MRH','TRANSPORT':'TRANSPORT','INCENDIE':'INCENDIE','IRD':'INCENDIE','VIE':'VIE','RC':'RC','RCP':'RC','MARITIME':'MARITIME','ASSISTANCE':'AUTRE','ENGIN':'AUTO'}

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

W("-- EVO02 RE-IMPORT COMPLET — genere le %s\n" % datetime.now())
W("\\set ON_ERROR_STOP on\nBEGIN;\n")

# ── S0. RESET metier (config societe + utilisateurs PRESERVES) ────────────────
W("""
-- S0. RESET (preserve: res_company, res_users, insurance_company, taxes,
--            risques, codes operations, banques, sequences, types anomalies)
DELETE FROM insurance_anomaly;
TRUNCATE TABLE insurance_settlement_imputation RESTART IDENTITY CASCADE;
TRUNCATE TABLE insurance_settlement RESTART IDENTITY CASCADE;
TRUNCATE TABLE insurance_claim RESTART IDENTITY CASCADE;
TRUNCATE TABLE insurance_operation RESTART IDENTITY CASCADE;
TRUNCATE TABLE insurance_receipt RESTART IDENTITY CASCADE;
TRUNCATE TABLE insurance_policy RESTART IDENTITY CASCADE;
DELETE FROM mail_message WHERE model IN ('insurance.claim','insurance.operation','insurance.receipt','insurance.policy','insurance.settlement','insurance.settlement.imputation');
DELETE FROM mail_followers WHERE res_model IN ('insurance.claim','insurance.operation','insurance.receipt','insurance.policy','insurance.settlement');
DELETE FROM account_move_line WHERE move_id IN (SELECT id FROM account_move WHERE partner_id IN (SELECT id FROM res_partner WHERE ref LIKE 'ORA-%'));
DELETE FROM account_move WHERE partner_id IN (SELECT id FROM res_partner WHERE ref LIKE 'ORA-%');
DELETE FROM res_partner WHERE ref LIKE 'ORA-%' AND id NOT IN (SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL);
""")

# ── S1. CLIENTS ───────────────────────────────────────────────────────────────
clients = tsv('PR_CLIENT_DATA_TABLE.tsv')
W("\n-- S1. CLIENTS (%d)\nCREATE TEMP TABLE tmp_cli(num text, nom text, street text, zip text, phone text, is_co boolean);\n" % len(clients))
rows = []
seen = set()
for c in clients:
    num = c.get('NUM_CLIENT', '')
    if not num or num in seen: continue
    seen.add(num)
    nom = c.get('RAISON_SOCIALE') or ((c.get('NOM','') + ' ' + c.get('PRENOM','')).strip()) or ('Client ' + num)
    rows.append('(%s,%s,%s,%s,%s,%s)' % (S(num), S(nom, 120), S(c.get('ADRESSE'), 120), S(c.get('CODE_POSTAL'), 12), S(c.get('TEL1') or c.get('MOBILE') or c.get('TEL2'), 30), 'TRUE' if c.get('TYPE_CLIENT') == 'E' else 'FALSE'))
values_block('INSERT INTO tmp_cli', rows)
W("""
INSERT INTO res_partner (name, ref, street, zip, phone, is_company, active, customer_rank, health_state, create_date, write_date, create_uid, write_uid, company_id, commercial_partner_id, complete_name)
SELECT t.nom, 'ORA-'||t.num, t.street, t.zip, t.phone, t.is_co, TRUE, 1, 'ok', NOW(), NOW(), 1, 1, NULL, NULL, t.nom
FROM tmp_cli t WHERE NOT EXISTS (SELECT 1 FROM res_partner p WHERE p.ref = 'ORA-'||t.num);
UPDATE res_partner SET commercial_partner_id = id WHERE ref LIKE 'ORA-%' AND commercial_partner_id IS NULL;
""")

# ── S2. POLICES ───────────────────────────────────────────────────────────────
polices = tsv('PR_POLICE_DATA_TABLE.tsv')
W("\n-- S2. POLICES (%d)\nCREATE TEMP TABLE tmp_pol(num text, num_cli text, compagnie text, branche text);\n" % len(polices))
rows, seen = [], set()
for p in polices:
    num = p.get('NUM_POLICE1', '')
    if not num or num in seen: continue
    seen.add(num)
    br = BRANCHE_MAP.get((p.get('BRANCHE') or '').strip().upper(), 'AUTRE')
    rows.append('(%s,%s,%s,%s)' % (S(num, 30), S(p.get('NUM_CLIENT')), S(p.get('COMPAGNIE'), 60), S(br)))
values_block('INSERT INTO tmp_pol', rows)
W("""
INSERT INTO insurance_policy (num_police, ref_interne, partner_id, payer_id, company_ins_id, branche, date_effect, date_echeance, state, type_client, currency_id, active, supp_log, raison_sociale, agence_courtier, create_date, write_date, create_uid, write_uid)
SELECT t.num, 'ORA-POL-'||t.num, p.id, p.id, c.id, t.branche, DATE '2015-01-01', DATE '2099-12-31', 'active', 'P', (SELECT id FROM res_currency WHERE name='TND'), TRUE, FALSE, p.name, 'Sfax', NOW(), NOW(), 1, 1
FROM tmp_pol t
JOIN res_partner p ON p.ref = 'ORA-'||t.num_cli
JOIN insurance_company c ON upper(c.name) = upper(t.compagnie);
-- polices dont la compagnie/le client n'a pas matche : comptage
CREATE TEMP TABLE tmp_pol_skipped AS
SELECT t.* FROM tmp_pol t WHERE NOT EXISTS (SELECT 1 FROM insurance_policy ip WHERE ip.num_police = t.num);
""")

# ── S3. QUITTANCES/MEMOIRES (PR_FACTURE) ──────────────────────────────────────
factures = tsv('PR_FACTURE_DATA_TABLE.tsv')
ops_all = tsv('PR_OPERATION_DATA_TABLE.tsv')
op_pol = {}
for o in ops_all:
    an, nf = o.get('ANNEE_FACT_PRIME',''), o.get('NUM_FACTURE_PRIME','')
    if an and nf and (an, nf) not in op_pol and o.get('NUM_POLICE'):
        op_pol[(an, nf)] = o['NUM_POLICE']
W("\n-- S3. QUITTANCES (%d)\nCREATE TEMP TABLE tmp_fact(annee text, num text, dt date, total numeric, total_reg numeric, encaisse boolean, num_cli text, pol_hint text);\n" % len(factures))
rows, seen = [], set()
for f in factures:
    an, nf = f.get('ANNEE_FACT',''), f.get('NUM_FACTURE','')
    if not an or not nf or (an, nf) in seen: continue
    seen.add((an, nf))
    rows.append('(%s,%s,%s,%s,%s,%s,%s,%s)' % (S(an), S(nf), D(f.get('DATE_FACT'), "'2015-01-01'"), N(f.get('TOTAL_FACT')), N(f.get('TOTAL_REG')), 'TRUE' if f.get('FACTURE_ENCAISSE')=='O' else 'FALSE', S(f.get('NUM_CLIENT')), S(op_pol.get((an,nf)), 30)))
values_block('INSERT INTO tmp_fact', rows)
W("""
-- police de repli pour les quittances sans rattachement
INSERT INTO insurance_policy (num_police, ref_interne, partner_id, payer_id, company_ins_id, branche, date_effect, date_echeance, state, type_client, currency_id, active, supp_log, create_date, write_date, create_uid, write_uid)
SELECT 'FALLBACK-MIG', 'FALLBACK-MIG', (SELECT min(id) FROM res_partner WHERE ref LIKE 'ORA-%'), (SELECT min(id) FROM res_partner WHERE ref LIKE 'ORA-%'), (SELECT min(id) FROM insurance_company), 'AUTRE', DATE '2015-01-01', DATE '2099-12-31', 'active', 'P', (SELECT id FROM res_currency WHERE name='TND'), TRUE, FALSE, NOW(), NOW(), 1, 1
WHERE NOT EXISTS (SELECT 1 FROM insurance_policy WHERE num_police='FALLBACK-MIG');

INSERT INTO insurance_receipt (name, policy_id, partner_id, payer_id, company_ins_id, date_emission, date_echeance, montant_prime, state, health_state, apply_timbre_fiscal, currency_id, active, notes, create_date, write_date, create_uid, write_uid)
SELECT 'ORA-FACT-'||t.annee||'-'||t.num,
       COALESCE(pol.id, polcli.id, (SELECT id FROM insurance_policy WHERE num_police='FALLBACK-MIG')),
       COALESCE(cli.id, polcli_p.id, (SELECT partner_id FROM insurance_policy WHERE num_police='FALLBACK-MIG')),
       COALESCE(cli.id, polcli_p.id, (SELECT partner_id FROM insurance_policy WHERE num_police='FALLBACK-MIG')),
       COALESCE(pol.company_ins_id, polcli.company_ins_id, (SELECT min(id) FROM insurance_company)),
       t.dt, t.dt, t.total,
       CASE WHEN t.encaisse THEN 'encaissee' WHEN t.total_reg > 0 THEN 'partielle' ELSE 'emise' END,
       'ok', FALSE, (SELECT id FROM res_currency WHERE name='TND'), TRUE,
       'Migre depuis PR_FACTURE '||t.annee||'/'||t.num, NOW(), NOW(), 1, 1
FROM tmp_fact t
LEFT JOIN insurance_policy pol ON pol.num_police = t.pol_hint
LEFT JOIN res_partner cli ON cli.ref = 'ORA-'||t.num_cli
LEFT JOIN LATERAL (SELECT ip.id, ip.company_ins_id, ip.partner_id FROM insurance_policy ip WHERE ip.partner_id = cli.id ORDER BY ip.id LIMIT 1) polcli ON TRUE
LEFT JOIN res_partner polcli_p ON polcli_p.id = polcli.partner_id;
""")
print('S0-S3 generes : clients=%d polices=%d quittances=%d' % (len(clients), len(polices), len(factures)))
out.flush()

# ── S4. OPERATIONS ────────────────────────────────────────────────────────────
W("\n-- S4. OPERATIONS (%d)\nCREATE TEMP TABLE tmp_ops(num text, num_pol text, num_cli text, code text, dt date, du date, au date, quitt text, attest text, veh text, prime numeric, comm numeric, hon numeric, desig text, nat text, an_p text, nf_p text);\n" % len(ops_all))
CODE_MAP = {'EMI':'EMI','REN':'REN','AVN':'AVN','SUS':'SUS','ANN':'ANN','RES':'RES','REM':'REM','CES':'CES'}
rows, seen = [], set()
for o in ops_all:
    num = o.get('NUM_OPERATION','')
    if not num or num in seen: continue
    seen.add(num)
    code = 'EMI'
    nat = (o.get('NATURE') or 'R')[:1]
    rows.append('(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)' % (
        S(num), S(o.get('NUM_POLICE'),30), S(o.get('NUM_CLIENT')), S(code),
        D(o.get('DATE_OP'),"'2015-01-01'"), D(o.get('DATE_VALIDITE_DU')), D(o.get('DATE_VALIDITE_AU')),
        S(o.get('NUM_QUITTANCE'),30), S(o.get('NUM_ATTESTATION'),20), S(o.get('VEHICULE'),30),
        N(o.get('MONTANT_PRIME')), N(o.get('COMMISSION')), N(o.get('MONTANT_HONORAIRE_HT')),
        S(o.get('DESIGNATION'),80), S(nat), S(o.get('ANNEE_FACT_PRIME')), S(o.get('NUM_FACTURE_PRIME'))))
values_block('INSERT INTO tmp_ops', rows)
W("""
INSERT INTO insurance_operation (name, internal_ref, policy_id, partner_id, company_ins_id, receipt_id, code_operation, date_op, date_validite_du, date_validite_au, num_quittance, num_attestation, vehicule, montant_prime, commission, montant_honoraire_ht, designation, nature, state, health_state, currency_id, active, supp_log, num_police, num_client, create_date, write_date, create_uid, write_uid)
SELECT 'ORA-OP-'||t.num, 'OP-MIG-'||lpad(t.num, 7, '0'),
       COALESCE(pol.id, polcli.id, (SELECT id FROM insurance_policy WHERE num_police='FALLBACK-MIG')),
       COALESCE(cli.id, pol.partner_id),
       COALESCE(pol.company_ins_id, (SELECT min(id) FROM insurance_company)),
       rcpt.id, t.code, t.dt, t.du, t.au, t.quitt, t.attest, t.veh,
       t.prime, t.comm, t.hon, t.desig, t.nat,
       CASE WHEN rcpt.id IS NOT NULL THEN 'invoiced' ELSE 'confirmed' END,
       'ok', (SELECT id FROM res_currency WHERE name='TND'), TRUE, FALSE,
       t.num_pol, t.num_cli, NOW(), NOW(), 1, 1
FROM tmp_ops t
LEFT JOIN insurance_policy pol ON pol.num_police = t.num_pol
LEFT JOIN res_partner cli ON cli.ref = 'ORA-'||t.num_cli
LEFT JOIN LATERAL (SELECT ip.id, ip.partner_id, ip.company_ins_id FROM insurance_policy ip WHERE ip.partner_id = cli.id ORDER BY ip.id LIMIT 1) polcli ON TRUE
LEFT JOIN insurance_receipt rcpt ON rcpt.name = 'ORA-FACT-'||t.an_p||'-'||t.nf_p;
""")

# ── S5. REGLEMENTS ────────────────────────────────────────────────────────────
regs = tsv('PR_REGELEMENT_DATA_TABLE.tsv')
W("\n-- S5. REGLEMENTS (%d)\nCREATE TEMP TABLE tmp_reg(num text, num_cli text, dt date, typ text, montant numeric, cheque text, impute boolean, impaye boolean, encaisse boolean);\n" % len(regs))
rows, seen = [], set()
for r in regs:
    num = r.get('NUM_REG_CLT','')
    if not num or num in seen: continue
    seen.add(num)
    typ = (r.get('TYPE_REG') or 'C')[:1]
    if typ not in 'CEVPA': typ = 'C'
    rows.append('(%s,%s,%s,%s,%s,%s,%s,%s,%s)' % (S(num), S(r.get('NUM_CLIENT')), D(r.get('DATE_REG'),"'2015-01-01'"), S(typ), N(r.get('MONTANT_REG')), S(r.get('NUM_CHEQUE'),20), 'TRUE' if r.get('IMPUTER')=='O' else 'FALSE', 'TRUE' if r.get('IMPAYE')=='O' else 'FALSE', 'TRUE' if r.get('ENCAISSE')=='O' else 'FALSE'))
values_block('INSERT INTO tmp_reg', rows)
W("""
INSERT INTO insurance_settlement (name, partner_id, date_reg, type_reg, montant_reg, num_cheque, state, imputer, health_state, currency_id, notes, create_date, write_date, create_uid, write_uid)
SELECT 'ORA-REG-'||t.num,
       COALESCE(cli.id, (SELECT partner_id FROM insurance_policy WHERE num_police='FALLBACK-MIG')),
       t.dt, t.typ, t.montant, t.cheque,
       CASE WHEN t.impaye THEN 'impaye' WHEN t.encaisse THEN 'encaisse' WHEN t.impute THEN 'regle' ELSE 'brouillon' END,
       t.impute, 'ok', (SELECT id FROM res_currency WHERE name='TND'),
       'Migre depuis PR_REGELEMENT '||t.num, NOW(), NOW(), 1, 1
FROM tmp_reg t
LEFT JOIN res_partner cli ON cli.ref = 'ORA-'||t.num_cli;
""")

# ── S6. LETTRAGE (PR_REG_FACTURE -> imputations, is_reconstructed) ───────────
rf = tsv('PR_REG_FACTURE_DATA_TABLE.tsv')
W("\n-- S6. LETTRAGE (%d)\nCREATE TEMP TABLE tmp_rf(num_reg text, annee text, num text, montant numeric, dt date, tiers boolean);\n" % len(rf))
rows = []
for r in rf:
    if (r.get('SUPP_LOG') or 'N') == 'O': continue
    rows.append('(%s,%s,%s,%s,%s,%s)' % (S(r.get('NUM_REG_CLT')), S(r.get('ANNEE_FACT')), S(r.get('NUM_FACTURE')), N(r.get('MONTANT_REG')), D(r.get('DATE_DERNIER_MAJ'),"'2015-01-01'"), 'TRUE' if r.get('TIERS')=='O' else 'FALSE'))
values_block('INSERT INTO tmp_rf', rows)
W("""
INSERT INTO insurance_settlement_imputation (settlement_id, receipt_id, montant_impute, date_imputation, is_reconstructed, health_state, notes, create_date, write_date, create_uid, write_uid)
SELECT s.id, rc.id, t.montant, t.dt, TRUE, 'ok',
       CASE WHEN t.tiers THEN 'TIERS Oracle' END, NOW(), NOW(), 1, 1
FROM tmp_rf t
JOIN insurance_settlement s ON s.name = 'ORA-REG-'||t.num_reg
JOIN insurance_receipt rc ON rc.name = 'ORA-FACT-'||t.annee||'-'||t.num;

-- Lettrages orphelins (reglement ou quittance inexistants) : table de reprise
CREATE TABLE IF NOT EXISTS evo02_lettrage_orphelin AS
SELECT t.* FROM tmp_rf t
WHERE NOT EXISTS (SELECT 1 FROM insurance_settlement s WHERE s.name='ORA-REG-'||t.num_reg)
   OR NOT EXISTS (SELECT 1 FROM insurance_receipt r WHERE r.name='ORA-FACT-'||t.annee||'-'||t.num);
""")

# ── S7. Controles de volumes ─────────────────────────────────────────────────
W("""
-- S7. CONTROLES
SELECT 'clients' AS objet, count(*) FROM res_partner WHERE ref LIKE 'ORA-%'
UNION ALL SELECT 'polices', count(*) FROM insurance_policy
UNION ALL SELECT 'quittances', count(*) FROM insurance_receipt
UNION ALL SELECT 'operations', count(*) FROM insurance_operation
UNION ALL SELECT 'reglements', count(*) FROM insurance_settlement
UNION ALL SELECT 'imputations', count(*) FROM insurance_settlement_imputation
UNION ALL SELECT 'lettrage_orphelin', count(*) FROM evo02_lettrage_orphelin
UNION ALL SELECT 'polices_non_matchees', count(*) FROM tmp_pol_skipped;
COMMIT;
ANALYZE;
""")
out.close()
print('SQL genere -> %s (%.1f Mo)' % (OUT, os.path.getsize(OUT) / 1048576.0))
