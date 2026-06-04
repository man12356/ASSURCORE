#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_journees_sql.py
Genere un fichier SQL d'import direct pour insurance_journal_enc.
Compatible Python 3.6+.

Usage:
    python3 generate_journees_sql.py
    python3 generate_journees_sql.py --out /tmp/journees.sql
"""

import csv, re, sys, io
from pathlib import Path
from datetime import date
from collections import defaultdict

CSV_FILE = Path(__file__).parent.parent / 'DATA_REEL_22-05-2026' / 'DATA_REEL' / 'PRIORITE_ENV_FACT_COMP_DATA_TABLE.csv'
OUT_FILE = Path(__file__).parent.parent / 'journees_import.sql'

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_french_num(s):
    if not s or str(s).strip() in ('', '""', '"'): return 0.0
    s = str(s).strip().strip('"').replace('\xa0', '').replace(' ', '')
    if s.count(',') == 1:
        s = s.replace(',', '.')
    elif s.count(',') > 1:
        parts = s.rsplit(',', 1)
        s = parts[0].replace(',', '') + '.' + parts[1]
    try: return float(s)
    except: return 0.0

def parse_date_fr(s):
    s = str(s).strip().strip('"')
    for fmt, is_2d in [('%d/%m/%y', True), ('%d/%m/%Y', False)]:
        try:
            import datetime
            d = datetime.datetime.strptime(s, fmt).date()
            if is_2d and d.year < 2000:
                d = d.replace(year=d.year + 100)
            return d.isoformat()
        except: pass
    return date.today().isoformat()

def sql_str(v):
    if v is None: return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"

# ── Mapping noms Oracle → Odoo ────────────────────────────────────────────────
COMPANY_MAP = {
    'BH ASSU':          'BH ASSU',
    'BH ASSURANCE':     'BH ASSURANCE',
    'LLOYD':            'LLOYD',
    'STAR':             'STAR',
    'Astree':           'Astree',
    'AL AMANA TAKAFUL': 'AL AMANA TAKAFUL',
    'CARTE':            'CARTE',
    'MAGHREBIA':        'MAGHREBIA',
    'MAE':              'MAE',
    'COMAR':            'COMAR',
    'BIAT ASS':         'BIAT ASS',
    'AMI':              'AMI',
}

# ── Parsing CSV ───────────────────────────────────────────────────────────────

def load_csv(path):
    records = []
    with io.open(str(path), encoding='utf-8') as f:
        raw = f.readlines()
    for line in raw[1:]:
        line = line.strip()
        if not line: continue
        try:
            parts = list(csv.reader([line]))[0]
            priorite    = int(parts[0])
            compagnie   = parts[1].strip('"')
            num_facture = int(parts[2])
            # Trouver la date comme ancre
            date_idx = None
            for i, p in enumerate(parts[3:], 3):
                if re.match(r'\d{2}/\d{2}/\d{2,4}', p.strip('"')):
                    date_idx = i
                    break
            if date_idx is None: continue
            montant   = parse_french_num(','.join(parts[3:date_idx]))
            date_modif= parse_date_fr(parts[date_idx])
            rest      = parts[date_idx + 1:]
            agence    = rest[1].strip('"') if len(rest) > 1 else 'Sfax'
            annee     = rest[2].strip('"') if len(rest) > 2 else ''
            annulee   = rest[6].strip('"') if len(rest) > 6 else 'N'
            raison_soc= rest[10].strip('"') if len(rest) > 10 else ''
            if annulee == 'O': continue  # Facture annulee
            records.append({
                'priorite': priorite, 'compagnie': compagnie,
                'num_facture': num_facture, 'montant': montant,
                'date': date_modif, 'agence': agence,
                'annee': annee, 'raison_soc': raison_soc,
            })
        except Exception as e:
            pass
    return records

def group_by_company(records):
    groups = defaultdict(lambda: {'total': 0.0, 'factures': [], 'date': None, 'agence': 'Sfax'})
    for r in records:
        c = r['compagnie']
        groups[c]['total']    += r['montant']
        groups[c]['factures'].append(r)
        groups[c]['agence']    = r['agence']
        if groups[c]['date'] is None or r['date'] > groups[c]['date']:
            groups[c]['date'] = r['date']
    return dict(groups)

def build_notes(factures):
    lines = ['Factures migreees depuis Oracle PRIORITE_ENV_FACT_COMP :']
    for f in sorted(factures, key=lambda x: x['num_facture']):
        lines.append('  N{} | {} | {:.3f} TND'.format(
            f['num_facture'], f['raison_soc'][:40], f['montant']))
    return '\n'.join(lines)

# ── Generation SQL ────────────────────────────────────────────────────────────

def generate_sql(groups, out_path):
    # Recuperer le prochain ID de sequence via SQL (sera inclus dans le fichier)
    with io.open(str(out_path), 'w', encoding='utf-8') as f:
        f.write("-- ============================================================\n")
        f.write("-- Import insurance_journal_enc depuis PRIORITE_ENV_FACT_COMP\n")
        f.write("-- {} journees d'encaissement — {:.3f} TND total\n".format(
            len(groups), sum(d['total'] for d in groups.values())))
        f.write("-- ============================================================\n\n")
        f.write("BEGIN;\n\n")

        for comp_oracle, data in sorted(groups.items(), key=lambda x: -x[1]['total']):
            comp_odoo = COMPANY_MAP.get(comp_oracle, comp_oracle)
            notes = build_notes(data['factures'])
            total = data['total']
            dt    = data['date'] or date.today().isoformat()
            agence= data['agence']

            f.write("-- Compagnie: {} ({} factures, {:.3f} TND)\n".format(
                comp_odoo, len(data['factures']), total))
            f.write("""INSERT INTO insurance_journal_enc (
    name, state, company_ins_id, date_creation,
    total_montant_enc, total_montant_enc_net,
    total_jour_commission, agence_courtier, notes,
    currency_id, create_date, write_date
)
SELECT
    'MIGR-' || UPPER(REPLACE({comp}, ' ', '_')),
    'ouvert',
    ic.id,
    {dt}::date,
    {total},
    {total},
    0,
    {agence},
    {notes},
    (SELECT id FROM res_currency WHERE name = 'TND' LIMIT 1),
    NOW(), NOW()
FROM insurance_company ic
WHERE LOWER(TRIM(ic.name)) = LOWER(TRIM({comp}))
  AND NOT EXISTS (
    SELECT 1 FROM insurance_journal_enc je
    WHERE je.company_ins_id = ic.id
      AND je.notes LIKE 'Factures migreees depuis Oracle%'
  )
LIMIT 1;\n\n""".format(
                comp   = sql_str(comp_odoo),
                dt     = sql_str(dt),
                total  = round(total, 3),
                agence = sql_str(agence),
                notes  = sql_str(notes),
            ))

        f.write("COMMIT;\n\n")
        f.write("-- Verification\n")
        f.write("SELECT ic.name AS compagnie, je.total_montant_enc AS montant_restant, je.state\n")
        f.write("FROM insurance_journal_enc je\n")
        f.write("JOIN insurance_company ic ON ic.id = je.company_ins_id\n")
        f.write("WHERE je.notes LIKE 'Factures migreees depuis Oracle%'\n")
        f.write("ORDER BY je.total_montant_enc DESC;\n")

    sys.stderr.write('SQL genere : {} journees dans {}\n'.format(len(groups), out_path))

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--csv', default=str(CSV_FILE))
    p.add_argument('--out', default=str(OUT_FILE))
    args = p.parse_args()

    sys.stderr.write('Lecture {}...\n'.format(args.csv))
    records = load_csv(Path(args.csv))
    sys.stderr.write('{} enregistrements charges\n'.format(len(records)))

    groups = group_by_company(records)
    sys.stderr.write('{} compagnies\n'.format(len(groups)))

    generate_sql(groups, Path(args.out))

    sys.stderr.write('\nCommandes pour injecter :\n')
    sys.stderr.write('  # Local:\n')
    sys.stderr.write('  docker exec -i assurcore_db psql -U odoo assurcore_db < journees_import.sql\n')
    sys.stderr.write('  # VPS:\n')
    sys.stderr.write('  scp journees_import.sql root@vps784643.ovh.net:/root/assurcore_prod/\n')
    sys.stderr.write('  docker exec -i assurcore_db psql -U odoo assurcore_db < /root/assurcore_prod/journees_import.sql\n')
