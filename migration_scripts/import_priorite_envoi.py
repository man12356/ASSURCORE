#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  import_priorite_envoi.py
  Import PRIORITE_ENV_FACT_COMP_DATA_TABLE.csv → insurance.journal.enc (Odoo)
================================================================================

Source  : PRIORITE_ENV_FACT_COMP_DATA_TABLE.csv
          (Factures de primes restant à envoyer aux compagnies au 17/04/2026)

Cible   : insurance.journal.enc — Journées d'Encaissement (AssurCore)

Logique :
  - Une ligne du CSV = une facture en attente d'envoi à la compagnie
  - On regroupe par (COMPAGNIE × ANNEE_FACT × CATEGORIE_FACTURE) pour créer
    une journée d'encaissement par compagnie/période
  - Chaque journée créée est en état 'ouvert' (à envoyer)
  - Idempotent : vérifie existence avant création (via notes contenant NUM_FACTURE)

Usage :
    python import_priorite_envoi.py
    python import_priorite_envoi.py --dry-run
    python import_priorite_envoi.py --url https://assurcore.metadidomi.com
================================================================================
"""

import xmlrpc.client
import csv
import re
import sys
import logging
import argparse
from datetime import date
from collections import defaultdict
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

ODOO_URL      = 'https://assurcore.metadidomi.com'
ODOO_DB       = 'assurcore_db'
ODOO_USER     = 'admin'
ODOO_PASSWORD = 'admin'

CSV_FILE      = Path(__file__).parent.parent / 'DATA_REEL_22-05-2026' / 'DATA_REEL' / 'PRIORITE_ENV_FACT_COMP_DATA_TABLE.csv'

# Mapping noms Oracle → noms Odoo (à ajuster si les noms diffèrent en base)
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

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('import_priorite_envoi.log', encoding='utf-8', mode='a'),
    ],
)
log = logging.getLogger('assurcore.etl.envoi')

# ══════════════════════════════════════════════════════════════════════════════
#  PARSING
# ══════════════════════════════════════════════════════════════════════════════

def parse_french_num(s: str) -> float:
    """Convertit '320,413' ou '1 234,567' (locale française) en float Python."""
    if not s or s.strip() in ('', '""', '"'):
        return 0.0
    s = s.strip().strip('"').replace('\xa0', '').replace(' ', '')
    if s.count(',') == 1:
        s = s.replace(',', '.')
    elif s.count(',') > 1:
        parts = s.rsplit(',', 1)
        s = parts[0].replace(',', '') + '.' + parts[1]
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_date(s: str):
    """Convertit 'DD/MM/YY' ou 'DD/MM/YYYY' en date Python."""
    s = s.strip().strip('"')
    for fmt in ('%d/%m/%y', '%d/%m/%Y'):
        try:
            d = date(*[int(x) for x in __import__('datetime').datetime.strptime(s, fmt).timetuple()[:3]])
            # Corriger l'ambiguïté siècle (26 → 2026)
            if d.year < 2000:
                d = d.replace(year=d.year + 100)
            return d
        except Exception:
            pass
    return date.today()


def load_csv(path: Path) -> list[dict]:
    """
    Parse le CSV avec décimales françaises (virgule = séparateur décimal).
    Ancre de parsing : cherche la date DD/MM/YY pour séparer les champs montants.
    Retourne une liste de dicts.
    """
    records = []
    with open(path, encoding='utf-8') as f:
        raw = f.readlines()

    skipped = 0
    for line in raw[1:]:  # skip header
        line = line.strip()
        if not line:
            continue
        try:
            parts = list(csv.reader([line]))[0]

            priorite    = int(parts[0])
            compagnie   = parts[1].strip('"')
            num_facture = int(parts[2])

            # Trouver la date comme ancre (DD/MM/YY)
            date_idx = None
            for i, p in enumerate(parts[3:], 3):
                if re.match(r'\d{2}/\d{2}/\d{2,4}', p.strip('"')):
                    date_idx = i
                    break
            if date_idx is None:
                skipped += 1
                continue

            montant_str = ','.join(parts[3:date_idx])
            montant     = parse_french_num(montant_str)
            date_modif  = parse_date(parts[date_idx])

            rest          = parts[date_idx + 1:]
            utilisateur   = rest[0].strip('"')  if len(rest) > 0 else ''
            agence        = rest[1].strip('"')  if len(rest) > 1 else ''
            annee         = rest[2].strip('"')  if len(rest) > 2 else ''
            cat_facture   = rest[3].strip('"')  if len(rest) > 3 else ''
            num_edit      = rest[4].strip('"')  if len(rest) > 4 else ''
            type_facture  = rest[5].strip('"')  if len(rest) > 5 else ''
            annulee       = rest[6].strip('"')  if len(rest) > 6 else 'N'
            type_client   = rest[7].strip('"')  if len(rest) > 7 else ''
            num_client    = rest[8].strip('"')  if len(rest) > 8 else ''
            attr_client   = rest[9].strip('"')  if len(rest) > 9 else ''
            raison_soc    = rest[10].strip('"') if len(rest) > 10 else ''
            total_pos_str = ','.join(rest[11:]) if len(rest) > 11 else '0'
            total_pos     = parse_french_num(total_pos_str)

            if annulee == 'O':
                skipped += 1
                continue  # Facture annulée → ignorer

            records.append({
                'priorite':    priorite,
                'compagnie':   compagnie,
                'num_facture': num_facture,
                'montant':     montant,
                'date':        date_modif,
                'utilisateur': utilisateur,
                'agence':      agence,
                'annee':       annee,
                'cat_facture': cat_facture,
                'num_edit':    num_edit,
                'type_facture': type_facture,
                'type_client': type_client,
                'num_client':  num_client,
                'raison_soc':  raison_soc,
                'total_pos':   total_pos,
            })
        except Exception as e:
            log.debug('Ligne ignorée : %s — %s', line[:60], e)
            skipped += 1

    log.info('CSV chargé : %d enregistrements, %d ignorés', len(records), skipped)
    return records


def group_by_company(records: list[dict]) -> dict:
    """
    Regroupe les factures par compagnie.
    Retourne : { compagnie: { 'total': float, 'factures': [...], 'date': date } }
    """
    groups = defaultdict(lambda: {'total': 0.0, 'factures': [], 'date': None})
    for r in records:
        comp = r['compagnie']
        groups[comp]['total']    += r['montant']
        groups[comp]['factures'].append(r)
        # Garder la date la plus récente
        if groups[comp]['date'] is None or r['date'] > groups[comp]['date']:
            groups[comp]['date'] = r['date']
    return dict(groups)


# ══════════════════════════════════════════════════════════════════════════════
#  XMLRPC
# ══════════════════════════════════════════════════════════════════════════════

class OdooRPC:
    def __init__(self, url, db, user, password):
        self.url      = url
        self.db       = db
        self.password = password
        self._uid     = None
        self._common  = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common', allow_none=True)
        self._models  = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object', allow_none=True)

    def connect(self):
        uid = self._common.authenticate(self.db, ODOO_USER, self.password, {})
        if not uid:
            raise ConnectionError('Authentification Odoo échouée')
        self._uid = uid
        log.info('Connecté à Odoo (uid=%d) — %s', uid, self.url)
        return uid

    def search(self, model, domain):
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, 'search', [domain],
        )

    def search_read(self, model, domain, fields):
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, 'search_read', [domain], {'fields': fields},
        )

    def create(self, model, vals):
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, 'create', [vals],
        )

    def write(self, model, ids, vals):
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, 'write', [ids, vals],
        )


# ══════════════════════════════════════════════════════════════════════════════
#  IMPORT
# ══════════════════════════════════════════════════════════════════════════════

def build_notes(factures: list[dict]) -> str:
    """Génère les notes détaillées de la journée (liste des factures)."""
    lines = ['Factures migrées depuis Oracle PRIORITE_ENV_FACT_COMP :']
    for f in sorted(factures, key=lambda x: x['num_facture']):
        lines.append(
            f"  N°{f['num_facture']} | {f['compagnie']} | "
            f"{f['raison_soc']} ({f['num_client']}) | "
            f"{f['montant']:.3f} TND | Édit:{f['num_edit']}"
        )
    return '\n'.join(lines)


def import_envoi(odoo: OdooRPC, groups: dict, dry_run: bool) -> dict:
    """
    Crée ou met à jour les journées d'encaissement dans Odoo.
    Retourne un résumé { created, updated, skipped }.
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    # Charger le dictionnaire des compagnies Odoo
    comp_records = odoo.search_read(
        'insurance.company', [], ['id', 'name']
    )
    comp_index = {r['name']: r['id'] for r in comp_records}
    comp_index_lower = {r['name'].lower().strip(): r['id'] for r in comp_records}
    log.info('Compagnies Odoo disponibles : %s', list(comp_index.keys()))

    for comp_name, data in groups.items():
        odoo_comp_name = COMPANY_MAP.get(comp_name, comp_name)
        comp_id = comp_index.get(odoo_comp_name)

        # Essai avec casse insensible
        if not comp_id:
            comp_id = comp_index_lower.get(odoo_comp_name.lower().strip())

        if not comp_id:
            log.warning('Compagnie introuvable dans Odoo : "%s" → SKIP', comp_name)
            stats['skipped'] += 1
            continue

        factures  = data['factures']
        total     = data['total']
        date_jrnl = data['date']
        notes     = build_notes(factures)
        ref       = f'MIGR-ENVOI-{comp_name[:20].upper().replace(" ", "_")}'

        # Vérifier si une journée de migration existe déjà pour cette compagnie
        existing = odoo.search_read(
            'insurance.journal.enc',
            [('company_ins_id', '=', comp_id),
             ('notes', 'like', 'Factures migrées depuis Oracle')],
            ['id', 'name', 'total_montant_enc'],
        )

        vals = {
            'company_ins_id':    comp_id,
            'date_creation':     date_jrnl.isoformat(),
            'total_montant_enc': total,
            'total_montant_enc_net': total,  # pas de commission connue → net = brut
            'state':             'ouvert',
            'notes':             notes,
            'agence_courtier':   'Sfax',
        }

        if dry_run:
            log.info('[DRY-RUN] %s | %d factures | %.3f TND | comp_id=%d',
                     comp_name, len(factures), total, comp_id)
            stats['created'] += 1
            continue

        if existing:
            odoo_id = existing[0]['id']
            odoo.write('insurance.journal.enc', [odoo_id], vals)
            log.info('MàJ  journée id=%d — %s — %.3f TND (%d factures)',
                     odoo_id, comp_name, total, len(factures))
            stats['updated'] += 1
        else:
            try:
                new_id = odoo.create('insurance.journal.enc', vals)
                log.info('CREE journée id=%d — %s — %.3f TND (%d factures)',
                         new_id, comp_name, total, len(factures))
                stats['created'] += 1
            except Exception as e:
                log.error('ERREUR création journée %s : %s', comp_name, e)
                stats['errors'] += 1

    return stats


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(description='Import PRIORITE_ENV_FACT_COMP → Odoo')
    p.add_argument('--dry-run', action='store_true', help='Simulation sans écriture')
    p.add_argument('--url',     default=ODOO_URL,    help='URL Odoo (défaut: prod)')
    p.add_argument('--file',    default=str(CSV_FILE), help='Chemin CSV source')
    return p.parse_args()


def main():
    args = parse_args()

    log.info('═══════════════════════════════════════════════════════')
    log.info('  Import PRIORITE_ENV_FACT_COMP → insurance.journal.enc')
    log.info('  URL    : %s', args.url)
    log.info('  Fichier: %s', args.file)
    log.info('  Mode   : %s', 'DRY-RUN' if args.dry_run else 'IMPORT RÉEL')
    log.info('═══════════════════════════════════════════════════════')

    # ── 1. Charger le CSV ────────────────────────────────────────────────────
    csv_path = Path(args.file)
    if not csv_path.exists():
        log.error('Fichier introuvable : %s', csv_path)
        sys.exit(1)

    records = load_csv(csv_path)
    if not records:
        log.error('Aucun enregistrement parsé. Vérifiez le fichier.')
        sys.exit(1)

    # ── 2. Résumé avant import ───────────────────────────────────────────────
    groups = group_by_company(records)
    log.info('')
    log.info('Résumé par compagnie :')
    total_global = 0
    for comp, d in sorted(groups.items(), key=lambda x: -x[1]['total']):
        log.info('  %-25s  %3d factures   %12.3f TND', comp, len(d['factures']), d['total'])
        total_global += d['total']
    log.info('  %-25s  %3d factures   %12.3f TND', 'TOTAL', len(records), total_global)
    log.info('')

    if args.dry_run:
        log.info('[DRY-RUN] Parsing OK — aucune écriture en base.')
        log.info('%d journées seraient créées dans Odoo.', len(groups))
        return

    # ── 3. Connexion Odoo ────────────────────────────────────────────────────
    global ODOO_URL
    ODOO_URL = args.url
    odoo = OdooRPC(args.url, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    try:
        odoo.connect()
    except Exception as e:
        log.error('Connexion Odoo échouée : %s', e)
        sys.exit(1)

    # ── 4. Import ────────────────────────────────────────────────────────────
    stats = import_envoi(odoo, groups, dry_run=False)

    # ── 5. Résumé final ──────────────────────────────────────────────────────
    log.info('')
    log.info('═══════════════════════════════════════════════════════')
    log.info('  IMPORT TERMINÉ')
    log.info('  Créées  : %d journées', stats['created'])
    log.info('  Mises à jour : %d', stats['updated'])
    log.info('  Ignorées (compagnie introuvable) : %d', stats['skipped'])
    log.info('  Erreurs : %d', stats['errors'])
    log.info('═══════════════════════════════════════════════════════')

    if stats['errors'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
