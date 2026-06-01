#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
do_lettrage_sql.py — Lettrage direct SQL (contourne Odoo XML-RPC)
Lie insurance_settlement.receipt_id via PostgreSQL directement.
Beaucoup plus rapide que XML-RPC pour 22844 liaisons.

Usage:
    python do_lettrage_sql.py
"""

import subprocess
import sys
from pathlib import Path
from collections import defaultdict

DATA_DIR    = Path(__file__).parent.parent / 'DATA_REEL_22-05-2026' / 'DATA_REEL'
CONTAINER   = 'assurcore_db'
DB_USER     = 'odoo'
DB_NAME     = 'assurcore_db'
SEPARATOR   = '\t'
ENCODING    = 'utf-8'

def run_sql(sql: str) -> str:
    result = subprocess.run(
        ['docker', 'exec', '-i', CONTAINER,
         'psql', '-U', DB_USER, '-d', DB_NAME, '-t', '-c', sql],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f'  SQL ERROR: {result.stderr.strip()}')
    return result.stdout.strip()

def run_sql_file(filepath: str) -> str:
    result = subprocess.run(
        ['docker', 'exec', '-i', CONTAINER,
         'psql', '-U', DB_USER, '-d', DB_NAME,
         '-v', 'ON_ERROR_STOP=0', '-f', '/tmp/lettrage.sql'],
        capture_output=True, text=True
    )
    return result.stdout + result.stderr

def read_tsv(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if not path.exists():
        # Try glob
        matches = list(DATA_DIR.glob(f'*{filename}*'))
        if not matches:
            print(f'  ⚠ Fichier introuvable: {filename}')
            return []
        path = matches[0]
    rows = []
    with open(path, 'r', encoding=ENCODING, errors='replace') as f:
        lines = f.readlines()
    if not lines:
        return []
    headers = [h.strip().strip('"') for h in lines[0].rstrip('\n\r').split(SEPARATOR)]
    for line in lines[1:]:
        parts = [p.strip().strip('"') for p in line.rstrip('\n\r').split(SEPARATOR)]
        if len(parts) == len(headers) and any(parts):
            rows.append(dict(zip(headers, parts)))
    return rows

def main():
    print('=' * 60)
    print('  Lettrage SQL direct — AssurCore Migration')
    print('=' * 60)

    # 1. Lire PR_REG_FACTURE
    print('\n[1/4] Lecture PR_REG_FACTURE...')
    rows = read_tsv('PR_REG_FACTURE_DATA_TABLE.tsv')
    print(f'  {len(rows)} liaisons règlement↔facture')

    if not rows:
        print('  ✗ Aucune donnée trouvée.')
        sys.exit(1)

    # 2. Construire les paires (settlement_name, receipt_name)
    print('\n[2/4] Construction des paires...')
    pairs: dict[str, str] = {}  # settlement_name -> receipt_name
    for row in rows:
        num_reg  = row.get('NUM_REG_CLT', '').strip()
        annee    = row.get('ANNEE_FACT', '').strip()
        num_fact = row.get('NUM_FACTURE', '').strip()
        supp     = row.get('SUPP_LOG', 'N').strip()
        if not num_reg or not annee or not num_fact or supp == 'O':
            continue
        sett_name    = f'ORA-REG-{num_reg}'
        receipt_name = f'ORA-FACT-{annee}-{num_fact}'
        pairs[sett_name] = receipt_name

    print(f'  {len(pairs)} paires valides construites')

    # 3. Générer le SQL de mise à jour
    print('\n[3/4] Génération du SQL...')

    # Créer une table temporaire et faire un UPDATE jointé
    lines = [
        'BEGIN;',
        '',
        'CREATE TEMP TABLE lettrage_tmp (sett_name TEXT, receipt_name TEXT);',
        '',
        'INSERT INTO lettrage_tmp (sett_name, receipt_name) VALUES',
    ]

    values = []
    for sett_name, receipt_name in pairs.items():
        # Escape single quotes
        s = sett_name.replace("'", "''")
        r = receipt_name.replace("'", "''")
        values.append(f"  ('{s}', '{r}')")

    lines.append(',\n'.join(values) + ';')
    lines.append('')

    # UPDATE insurance_settlement
    lines += [
        '-- Lier les règlements aux quittances',
        'UPDATE insurance_settlement s',
        '  SET receipt_id = r.id,',
        '      imputer    = true',
        'FROM lettrage_tmp lt',
        'JOIN insurance_receipt r ON r.name = lt.receipt_name',
        'WHERE s.name = lt.sett_name',
        '  AND (s.receipt_id IS NULL OR s.receipt_id != r.id);',
        '',
        '-- Compter les liaisons créées',
        "SELECT 'Settlements liés: ' || COUNT(*) FROM insurance_settlement WHERE receipt_id IS NOT NULL;",
        '',
        '-- Mettre à jour le statut des quittances encaissées',
        "UPDATE insurance_receipt r",
        "  SET state = 'encaissee'",
        "FROM (",
        "  SELECT DISTINCT receipt_id FROM insurance_settlement WHERE receipt_id IS NOT NULL",
        ") linked",
        "WHERE r.id = linked.receipt_id",
        "  AND r.state != 'encaissee';",
        '',
        "SELECT 'Quittances encaissées: ' || COUNT(*) FROM insurance_receipt WHERE state = 'encaissee';",
        '',
        'COMMIT;',
        '',
        'DROP TABLE IF EXISTS lettrage_tmp;',
    ]

    sql_content = '\n'.join(lines)

    # Écrire le SQL dans un fichier temporaire dans le conteneur
    sql_path = Path(__file__).parent / 'lettrage_tmp.sql'
    with open(sql_path, 'w', encoding='utf-8') as f:
        f.write(sql_content)

    print(f'  SQL généré: {len(lines)} lignes, {len(values)} paires')

    # 4. Copier et exécuter dans le conteneur
    print('\n[4/4] Exécution SQL dans PostgreSQL...')

    # Copy file to container
    cp_result = subprocess.run(
        ['docker', 'cp',
         str(sql_path),
         f'{CONTAINER}:/tmp/lettrage.sql'],
        capture_output=True, text=True
    )
    if cp_result.returncode != 0:
        print(f'  ✗ docker cp échoué: {cp_result.stderr}')
        sys.exit(1)

    result = subprocess.run(
        ['docker', 'exec', CONTAINER,
         'psql', '-U', DB_USER, '-d', DB_NAME,
         '-v', 'ON_ERROR_STOP=0', '-f', '/tmp/lettrage.sql'],
        capture_output=True, text=True
    )

    output = result.stdout + result.stderr
    for line in output.splitlines():
        if line.strip():
            print(f'  {line}')

    print('\n' + '=' * 60)
    print('  Vérification finale')
    print('=' * 60)
    r1 = run_sql("SELECT COUNT(*) FROM insurance_settlement WHERE receipt_id IS NOT NULL;")
    r2 = run_sql("SELECT COUNT(*) FROM insurance_receipt WHERE state = 'encaissee';")
    r3 = run_sql("SELECT COUNT(*) FROM insurance_receipt WHERE state = 'emise';")
    print(f'  Règlements liés à une quittance : {r1.strip()}')
    print(f'  Quittances encaissées           : {r2.strip()}')
    print(f'  Quittances encore émises        : {r3.strip()}')
    print()

if __name__ == '__main__':
    main()
