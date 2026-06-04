#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_operations_sql.py
Genere un fichier SQL d'import direct pour insurance_operation.
Compatible Python 3.6+. Pas de type hints modernes.
Usage: python3 generate_operations_sql.py > /tmp/operations.sql
"""

import csv, re, sys, io
from pathlib import Path
from datetime import date, timedelta

DATA_FILE = Path(__file__).parent.parent / 'DATA_ASS.txt'
OUT_FILE  = Path(__file__).parent.parent / 'operations_import.sql'

SEPARATOR = '\t'
ENCODING  = 'utf-8'

# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_str(v, maxlen=None):
    if v is None: return None
    v = str(v).strip().strip('"')
    if not v or v.lower() in ('null', 'none', '""', "''"):
        return None
    if maxlen:
        v = v[:maxlen]
    return v

def parse_float(v):
    if not v: return 0.0
    v = str(v).strip().strip('"').replace(' ', '').replace(',', '.')
    try: return float(v)
    except: return 0.0

def parse_date(v):
    if not v: return None
    v = str(v).strip().strip('"')
    for fmt, is_2digit in [('%d/%m/%y', True), ('%d/%m/%Y', False)]:
        try:
            import datetime
            d = datetime.datetime.strptime(v, fmt).date()
            if is_2digit and d.year < 2000:
                d = d.replace(year=d.year + 100)
            return d.isoformat()
        except: pass
    return None

def oracle_bool(v):
    return str(v).strip().upper() in ('O', 'Y', '1', 'TRUE', 'OUI')

def map_code_operation(code):
    mapping = {
        'NV': 'NV', 'AVN': 'AVN', 'RES': 'RES', 'SUS': 'SUS',
        'REM': 'REM', 'ECH': 'ECH', 'ANN': 'ANN', 'REG': 'REG',
        'CX': 'CX',
    }
    return mapping.get(code.upper() if code else '', 'NV')

def sql_str(v):
    """Echapper une chaine pour SQL."""
    if v is None: return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"

def sql_num(v):
    if v is None or v == 0.0: return 'NULL'
    return str(v)

def sql_bool(v):
    return 'TRUE' if v else 'FALSE'

# ── Parsing DATA_ASS.txt ──────────────────────────────────────────────────────

def parse_data_file(filepath):
    """Parse DATA_ASS.txt et retourne le bloc PR_OPERATION."""
    current_block = None
    current_cols  = []
    blocks = {}

    BLOCK_SIGNATURES = {
        'PR_OPERATION': {'NUM_OPERATION', 'CODE_OPERATION1', 'NUM_POLICE', 'MONTANT_PRIME'},
        'PR_POLICE':    {'NUM_POLICE', 'TYPE_CLIENT', 'NUM_CLIENT'},
    }

    with io.open(str(filepath), encoding=ENCODING, errors='replace') as fh:
        for raw_line in fh:
            line = raw_line.rstrip('\n').rstrip('\r')
            if not line.strip():
                continue

            parts = line.split(SEPARATOR)
            if len(parts) < 2:
                continue

            cols = [p.strip().strip('"') for p in parts]

            # Detection entete de bloc
            matched_block = None
            for bname, required in BLOCK_SIGNATURES.items():
                if required.issubset(set(cols)):
                    matched_block = bname
                    break

            if matched_block:
                current_block = matched_block
                current_cols  = cols
                if current_block not in blocks:
                    blocks[current_block] = []
                continue

            if current_block and current_cols:
                if len(parts) >= len(current_cols):
                    row = {}
                    for i, col in enumerate(current_cols):
                        row[col] = parts[i].strip().strip('"') if i < len(parts) else ''
                    blocks[current_block].append(row)

    return blocks


# ── Generation SQL ────────────────────────────────────────────────────────────

def generate_sql(operations, out_path):
    total = len(operations)
    written = 0
    skipped = 0

    with io.open(str(out_path), 'w', encoding='utf-8') as f:
        # Header
        f.write("-- ============================================================\n")
        f.write("-- Import insurance_operation depuis Oracle ASSKAREKAMOUN\n")
        f.write("-- Genere automatiquement — NE PAS MODIFIER\n")
        f.write("-- ============================================================\n\n")
        f.write("BEGIN;\n\n")
        f.write("-- Desactiver les triggers pour accelrer l'import\n")
        f.write("SET session_replication_role = replica;\n\n")

        batch = []
        BATCH_SIZE = 500

        for row in operations:
            num_op    = clean_str(row.get('NUM_OPERATION', ''))
            num_police= clean_str(row.get('NUM_POLICE', ''))
            if not num_op or not num_police:
                skipped += 1
                continue

            ora_name  = 'ORA-OP-' + num_op
            code_op   = map_code_operation(clean_str(row.get('CODE_OPERATION1', ''), 3) or '')
            date_op   = parse_date(row.get('DATE_OP', '')) or date.today().isoformat()
            du        = parse_date(row.get('DATE_VALIDITE_DU', ''))
            au        = parse_date(row.get('DATE_VALIDITE_AU', ''))

            # Corriger incoherence de dates
            if du and au and au < du:
                au = du
            if du and au and au <= du:
                try:
                    from datetime import date as dt
                    au = (dt.fromisoformat(au) + timedelta(days=1)).isoformat()
                except:
                    pass

            montant   = parse_float(row.get('MONTANT_PRIME', '0'))
            commission= parse_float(row.get('COMMISSION', '0'))
            hon_ht    = parse_float(row.get('MONTANT_HONORAIRE_HT', '0'))
            active    = not oracle_bool(row.get('SUPP_LOG', 'N'))
            annee_p   = int(parse_float(row.get('ANNEE_FACT_PRIME', '0')))
            annee_h   = int(parse_float(row.get('ANNEE_FACT_HON', '0')))
            num_edit_p= clean_str(row.get('NUM_EDIT_FACTURE_PRIME', ''), 30)
            num_edit_h= clean_str(row.get('NUM_EDIT_FACTURE_HON', ''), 30)
            cat_p     = clean_str(row.get('CATEGORIE_FACTURE_PRIME', ''), 20)
            cat_h     = clean_str(row.get('CATEGORIE_FACTURE_HON', ''), 20)
            attr_cli  = clean_str(row.get('ATTRIBUT_CLIENT', ''), 50)
            type_cli  = clean_str(row.get('TYPE_CLIENT', ''), 1)
            num_cli   = clean_str(row.get('NUM_CLIENT', ''))
            desig     = clean_str(row.get('DESIGNATION', ''), 250)
            num_quitt = clean_str(row.get('NUM_QUITTANCE', ''), 30)
            num_att   = clean_str(row.get('NUM_ATTESTATION', ''), 20)
            vehicule  = clean_str(row.get('VEHICULE', ''), 30)
            nature    = clean_str(row.get('NATURE', 'R'), 1) or 'R'

            sql = """INSERT INTO insurance_operation (
    name, policy_id, code_operation, date_op,
    date_validite_du, date_validite_au,
    num_quittance, num_attestation, vehicule,
    montant_prime, commission, montant_honoraire_ht,
    designation, nature, state, active,
    annee_fact_prime, num_edit_facture_prime,
    annee_fact_hon, num_edit_facture_hon,
    categorie_facture_prime, categorie_facture_hon,
    attribut_client, type_client, num_client,
    num_police, create_date, write_date
) SELECT
    {name},
    pol.id,
    {code_op},
    {date_op}::date,
    {du}::date,
    {au}::date,
    {num_quitt},
    {num_att},
    {vehicule},
    {montant},
    {commission},
    {hon_ht},
    {desig},
    {nature},
    'confirmed',
    {active},
    {annee_p},
    {num_edit_p},
    {annee_h},
    {num_edit_h},
    {cat_p},
    {cat_h},
    {attr_cli},
    {type_cli},
    {num_cli},
    {num_police},
    NOW(), NOW()
FROM insurance_policy pol
WHERE pol.num_police = {num_police_val}
ON CONFLICT DO NOTHING;""".format(
                name        = sql_str(ora_name),
                code_op     = sql_str(code_op),
                date_op     = sql_str(date_op),
                du          = sql_str(du),
                au          = sql_str(au),
                num_quitt   = sql_str(num_quitt),
                num_att     = sql_str(num_att),
                vehicule    = sql_str(vehicule),
                montant     = parse_float(row.get('MONTANT_PRIME', '0')),
                commission  = parse_float(row.get('COMMISSION', '0')),
                hon_ht      = parse_float(row.get('MONTANT_HONORAIRE_HT', '0')),
                desig       = sql_str(desig),
                nature      = sql_str(nature),
                active      = sql_bool(active),
                annee_p     = annee_p,
                num_edit_p  = sql_str(num_edit_p),
                annee_h     = annee_h,
                num_edit_h  = sql_str(num_edit_h),
                cat_p       = sql_str(cat_p),
                cat_h       = sql_str(cat_h),
                attr_cli    = sql_str(attr_cli),
                type_cli    = sql_str(type_cli),
                num_cli     = sql_str(num_cli),
                num_police  = sql_str(num_police),
                num_police_val = sql_str(num_police),
            )
            batch.append(sql)
            written += 1

            if len(batch) >= BATCH_SIZE:
                f.write('\n'.join(batch) + '\n\n')
                batch = []
                sys.stderr.write(f'\r  {written}/{total} generes...')
                sys.stderr.flush()

        if batch:
            f.write('\n'.join(batch) + '\n\n')

        # Footer
        f.write("\n-- Reactiver les triggers\n")
        f.write("SET session_replication_role = DEFAULT;\n\n")
        f.write("COMMIT;\n\n")
        f.write(f"-- Total genere : {written} operations, {skipped} ignores\n")
        f.write("SELECT COUNT(*) AS total_operations FROM insurance_operation;\n")

    sys.stderr.write(f'\nSQL genere : {written} operations dans {out_path}\n')
    return written, skipped


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--file', default=str(DATA_FILE))
    p.add_argument('--out',  default=str(OUT_FILE))
    args = p.parse_args()

    sys.stderr.write(f'Parsing {args.file}...\n')
    blocks = parse_data_file(Path(args.file))
    ops = blocks.get('PR_OPERATION', [])
    sys.stderr.write(f'PR_OPERATION : {len(ops)} lignes\n')

    written, skipped = generate_sql(ops, Path(args.out))
    sys.stderr.write(f'Fichier SQL : {args.out}\n')
    sys.stderr.write(f'Commande VPS :\n')
    sys.stderr.write(f'  docker exec -i assurcore_db psql -U odoo assurcore_db < operations_import.sql\n')
