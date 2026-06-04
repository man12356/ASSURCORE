#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_imputations_sql.py
Genere un fichier SQL pour migrer PR_COMPENSATION_REGLEMENT
vers insurance_settlement_imputation.

Compatible Python 3.6+.
Usage:
    python3 generate_imputations_sql.py
    python3 generate_imputations_sql.py --out /tmp/imputations.sql
"""

import csv, sys, io
from pathlib import Path
from datetime import date

CSV_FILE = Path(__file__).parent.parent / 'DATA_REEL_22-05-2026' / 'DATA_REEL' / 'PR_COMPENSATION_REGLEMENT_DATA_TABLE.tsv'
OUT_FILE = Path(__file__).parent.parent / 'imputations_import.sql'

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

def parse_num(s):
    if not s: return 0.0
    s = str(s).strip().strip('"').replace(' ', '').replace(',', '.')
    try: return float(s)
    except: return 0.0

def sql_str(v):
    if v is None or str(v).strip() in ('', '""', '"'): return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"

def load_csv(path):
    records = []
    with io.open(str(path), encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            num_reg   = row.get('NUM_REG_CLT', '').strip().strip('"')
            montant   = parse_num(row.get('MONTANT_COMPENSATION_PARTIEL') or
                                  row.get('MONTANT_PIECE_COMPENSATION', '0'))
            date_comp = parse_date_fr(row.get('DATE_COMP', ''))
            supp_log  = row.get('SUPP_LOG', 'N').strip().strip('"').upper()
            notes     = row.get('NOTES', '').strip().strip('"')

            if supp_log == 'O': continue
            if not num_reg or montant <= 0: continue

            records.append({
                'num_reg':   num_reg,
                'montant':   montant,
                'date_comp': date_comp,
                'notes':     notes or None,
            })
    return records

def generate_sql(records, out_path):
    with io.open(str(out_path), 'w', encoding='utf-8') as f:
        f.write("-- ==========================================================\n")
        f.write("-- Migration PR_COMPENSATION_REGLEMENT → insurance_settlement_imputation\n")
        f.write("-- {} lignes a traiter\n".format(len(records)))
        f.write("-- ==========================================================\n\n")
        f.write("BEGIN;\n\n")

        written = skipped = 0
        for r in records:
            # Recherche du settlement par nom (ORA-REG-NUM_REG ou reference similaire)
            # et d'une quittance via la compensation
            sql = """INSERT INTO insurance_settlement_imputation
    (settlement_id, receipt_id, montant_impute, date_imputation, notes, create_date, write_date)
SELECT
    s.id,
    rec.id,
    {montant},
    {date_comp}::date,
    {notes},
    NOW(), NOW()
FROM insurance_settlement s
JOIN insurance_receipt rec ON rec.id = s.receipt_id
WHERE s.name LIKE '%{num_reg}%'
  AND NOT EXISTS (
    SELECT 1 FROM insurance_settlement_imputation i
    WHERE i.settlement_id = s.id AND i.receipt_id = rec.id
      AND ABS(i.montant_impute - {montant}) < 0.01
  )
LIMIT 1;\n""".format(
                num_reg   = r['num_reg'],
                montant   = r['montant'],
                date_comp = sql_str(r['date_comp']),
                notes     = sql_str(r['notes']),
            )
            f.write(sql)
            written += 1

        f.write("\nCOMMIT;\n\n")
        f.write("-- Mise a jour du montant_restant sur les settlements\n")
        f.write("-- (sera recalcule automatiquement par le compute store=True)\n\n")
        f.write("SELECT COUNT(*) AS imputations_creees FROM insurance_settlement_imputation;\n")

    sys.stderr.write('SQL genere : {} lignes → {}\n'.format(written, out_path))

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--csv', default=str(CSV_FILE))
    p.add_argument('--out', default=str(OUT_FILE))
    args = p.parse_args()

    if not Path(args.csv).exists():
        sys.stderr.write('Fichier CSV introuvable : {}\n'.format(args.csv))
        sys.stderr.write('Note : ce fichier peut ne pas etre disponible localement.\n')
        sys.stderr.write('Les imputations seront creees manuellement via l\'interface Odoo.\n')
        sys.exit(0)

    records = load_csv(Path(args.csv))
    sys.stderr.write('{} compensations a migrer\n'.format(len(records)))
    generate_sql(records, Path(args.out))
