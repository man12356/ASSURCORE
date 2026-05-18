#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  import_assurcore_v2.py — ETL Phase 2 : Completion de la Migration
  Oracle ASSKAREKAMOUN → Odoo 17 AssurCore
================================================================================

Données importées dans cette phase :
  ÉTAPE 1 : insurance.risk        ← PR_RISQUE       (37  lignes)
  ÉTAPE 2 : insurance.operation.code ← Codes extraits de PR_OPERATION
  ÉTAPE 3 : res.partner update    ← PR_CLIENT       (3 726 lignes, mise à jour)
  ÉTAPE 4 : insurance.bank        ← PR_BANQUE       (11  lignes)
  ÉTAPE 5 : insurance.receipt     ← PR_FACTURE      (15 738 factures)
  ÉTAPE 6 : insurance.settlement  ← PR_REGELEMENT   (15 767 règlements)
  ÉTAPE 7 : Lettrage              ← PR_REG_FACTURE  (16 561 liaisons)
  ÉTAPE 8 : insurance.claim       ← PR_SINISTRE     (1   sinistre)

Philosophie :
  - Aucune perte de données : même les tables à 1 ligne sont migrées
  - Idempotence totale : relancer 2 fois = 0 doublon
  - Lettrage : PR_REG_FACTURE lie les règlements aux factures
    → met à jour le statut des insurance.receipt en 'encaissee'
    → calcule les vrais soldes clients

Usage :
    python import_assurcore_v2.py --dry-run
    python import_assurcore_v2.py
    python import_assurcore_v2.py --steps risques,clients,factures,lettrage
================================================================================
"""

import xmlrpc.client
import logging
import sys
import re
import argparse
from datetime import date
from pathlib import Path
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
#  ① CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

ODOO_URL      = 'http://localhost:8071'    # Adapter au port de votre instance
ODOO_DB       = 'assurcore_db'
ODOO_USER     = 'admin'
ODOO_PASSWORD = 'admin'

DATA_FILE  = Path(__file__).parent.parent / 'DATA_ASS.txt'
ENCODING   = 'utf-8'
SEPARATOR  = '\t'
BATCH_SIZE = 100
LOG_LEVEL  = logging.INFO

# ══════════════════════════════════════════════════════════════════════════════
#  ② LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('import_assurcore_v2.log', encoding='utf-8', mode='a'),
    ],
)
log = logging.getLogger('assurcore.etl.v2')

# ══════════════════════════════════════════════════════════════════════════════
#  ③ UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def parse_date(value: str) -> str | None:
    if not value or value.strip() in ('', 'NULL', 'null'):
        return None
    v = value.strip()
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', v)
    if m:
        day, month, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', v)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', v)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return None


def parse_float(value: str) -> float:
    if not value or value.strip() in ('', 'NULL', 'null'):
        return 0.0
    v = value.strip().replace('\xa0', '').replace(' ', '')
    if ',' in v and '.' not in v:
        v = v.replace(',', '.')
    elif ',' in v and '.' in v:
        v = v.replace('.', '').replace(',', '.')
    try:
        return float(v)
    except ValueError:
        return 0.0


def clean_str(value: str, max_len: int = 0) -> str:
    if not value or str(value).strip().upper() in ('', 'NULL'):
        return ''
    v = str(value).strip()
    if max_len and len(v) > max_len:
        v = v[:max_len]
    return v


# ══════════════════════════════════════════════════════════════════════════════
#  ④ PARSEUR MULTI-BLOCS
# ══════════════════════════════════════════════════════════════════════════════

TABLE_SIGNATURES_V2 = [
    # Tables de paramétrage
    ('PR_RISQUE',            {'RISQUE', 'BRANCHE'}),
    # PR_CODE_OPERATION reference (distinct from PR_OPERATION transactions)
    ('PR_CODE_OPERATION_REF', {'DESIGNATION', 'LIBELLE_HONORAIRE', 'DESCRIPTION',
                               'DATE_DERNIER_MAJ'}),
    # Clients complets
    ('PR_CLIENT',            {'TYPE_CLIENT', 'NUM_CLIENT', 'NOM', 'PRENOM',
                              'RAISON_SOCIALE', 'CIN', 'TEL1', 'MOBILE'}),
    # Banques
    ('PR_BANQUE',            {'BANQUE'}),
    # Factures
    ('PR_FACTURE',           {'ANNEE_FACT', 'NUM_FACTURE', 'NUM_CLIENT',
                              'DATE_FACT', 'TOTAL_FACT', 'FACTURE_ENCAISSE',
                              'TOTAL_REG'}),
    # Règlements
    ('PR_REGELEMENT',        {'NUM_REG_CLT', 'TYPE_CLIENT', 'NUM_CLIENT',
                              'DATE_REG', 'TYPE_REG', 'MONTANT_REG', 'NUM_CHEQUE'}),
    # Lettrage Règlement ↔ Facture
    ('PR_REG_FACTURE',       {'NUM_REG_CLT', 'ANNEE_FACT', 'NUM_FACTURE',
                              'MONTANT_REG', 'CATEGORIE_FACTURE'}),
    # Sinistre (1 ligne)
    ('PR_SINISTRE',          {'ANNEE_SIN', 'NUM_SINISTRE', 'NUM_POLICE',
                              'DATE_SINISTRE', 'COMPAGNIE', 'MONTANT_INDEMNITE'}),
    # Expert (1 ligne si présent)
    ('PR_EXPERT',            {'NUM_EXPERT', 'NOM_EXPERT', 'PRENOM_EXPERT'}),
]


def parse_data_file_v2(filepath: Path) -> dict[str, list[dict]]:
    """Parse DATA_ASS.txt ou un répertoire de fichiers .tsv et extrait les blocs nécessaires pour la Phase 2."""
    blocks: dict[str, list[dict]] = defaultdict(list)
    total = 0

    if filepath.is_dir():
        log.info('Lecture du répertoire de données %s …', filepath)
        # Définir la correspondance entre le nom du fichier et le nom du bloc attendu
        file_to_block = {
            'PR_RISQUE': 'PR_RISQUE',
            'PR_CODE_OPERATION': 'PR_OPERATION',  # Utilisé pour les codes opérations
            'PR_CLIENT': 'PR_CLIENT',
            'PR_BANQUE': 'PR_BANQUE',
            'PR_FACTURE': 'PR_FACTURE',
            'PR_REGELEMENT': 'PR_REGELEMENT',
            'PR_REG_FACTURE': 'PR_REG_FACTURE',
            'PR_SINISTRE': 'PR_SINISTRE',
            'PR_EXPERT': 'PR_EXPERT',
        }
        
        for tsv_file in filepath.glob('*.tsv'):
            base_name = tsv_file.name.replace('_DATA_TABLE.tsv', '').replace('.tsv', '')
            block_name = file_to_block.get(base_name)
            if not block_name:
                # Essayer une correspondance partielle si pas exacte
                for k, v in file_to_block.items():
                    if k in base_name:
                        block_name = v
                        break
            
            if not block_name:
                continue
                
            log.info('Lecture de la table %s depuis %s …', block_name, tsv_file.name)
            try:
                with open(tsv_file, 'r', encoding=ENCODING, errors='replace') as f:
                    lines = f.readlines()
                    if not lines:
                        continue
                    headers = [p.strip().strip('"') for p in lines[0].rstrip('\n\r').split(SEPARATOR)]
                    for line in lines[1:]:
                        line = line.rstrip('\n\r')
                        parts = [p.strip().strip('"') for p in line.split(SEPARATOR)]
                        if not any(parts) or len(parts) != len(headers):
                            continue
                        blocks[block_name].append(dict(zip(headers, parts)))
                        total += 1
            except Exception as exc:
                log.error('Erreur de lecture du fichier %s : %s', tsv_file.name, exc)
    else:
        log.info('Lecture de %s …', filepath)

        with open(filepath, 'r', encoding=ENCODING, errors='replace') as f:
            for lineno, raw_line in enumerate(f, 1):
                line = raw_line.rstrip('\n\r')
                parts = [p.strip().strip('"') for p in line.split(SEPARATOR)]
                if not any(parts):
                    continue

                upper_cnt = sum(
                    1 for p in parts
                    if p == p.upper() and re.match(r'^[A-Z][A-Z0-9_]*$', p) and len(p) > 1
                )
                is_header = upper_cnt >= len(parts) * 0.6 and len(parts) >= 2

                if is_header:
                    col_set = set(parts)
                    matched = None
                    for block_name, required in TABLE_SIGNATURES_V2:
                        if required.issubset(col_set):
                            matched = block_name
                            break
                    current_block = matched
                    current_cols = parts
                    continue

                if not current_block or not current_cols:
                    continue
                if len(parts) != len(current_cols):
                    continue

                blocks[current_block].append(dict(zip(current_cols, parts)))
                total += 1

    log.info('Parsing terminé : %d lignes utiles', total)
    for name, rows in sorted(blocks.items()):
        log.info('  %-30s : %6d lignes', name, len(rows))

    return dict(blocks)


# ══════════════════════════════════════════════════════════════════════════════
#  ⑤ CONNEXION ODOO
# ══════════════════════════════════════════════════════════════════════════════

class OdooRPC:
    def __init__(self, url, db, user, password, dry_run=False):
        self.db       = db
        self.password = password
        self.dry_run  = dry_run
        self._uid     = None
        self._common  = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common',
                                                   allow_none=True)
        self._models  = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object',
                                                   allow_none=True)

    def connect(self, user, password):
        uid = self._common.authenticate(self.db, user, password, {})
        if not uid:
            raise ConnectionError(f'Authentification échouée pour {user}@{self.db}')
        self._uid = uid
        version = self._common.version()
        log.info('Connecté — UID=%d | Odoo %s', uid,
                 version.get('server_version', '?'))
        return uid

    def execute(self, model, method, *args, **kwargs):
        if self.dry_run and method in ('create', 'write', 'unlink'):
            log.debug('[DRY-RUN] %s.%s', model, method)
            return [] if method == 'create' else True
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, method, list(args), kwargs
        )

    def ensure(self, model, domain, vals=None, create_vals=None) -> tuple[int, bool]:
        ids = self.execute(model, 'search', domain, limit=1)
        if ids:
            return ids[0], False
        actual_vals = vals if vals is not None else (create_vals or {})
        new_id = self.execute(model, 'create', actual_vals)
        return (new_id if isinstance(new_id, int) else new_id[0]), True

    def search_read(self, model, domain, fields, **kwargs):
        return self.execute(model, 'search_read', domain, fields=fields, **kwargs) or []

    def batch_write(self, model, ids, vals):
        if self.dry_run:
            return True
        if ids:
            self.execute(model, 'write', ids, vals)


# ══════════════════════════════════════════════════════════════════════════════
#  ⑥ ÉTAPES ETL
# ══════════════════════════════════════════════════════════════════════════════

def load_operation_policy_mapping(filepath: Path) -> dict[str, str]:
    """
    Lit PR_OPERATION (soit dans PR_OPERATION_DATA_TABLE.tsv, soit dans DATA_ASS.txt)
    et extrait le dictionnaire mapping (annee_fact|num_facture) -> num_police.
    """
    mapping = {}
    if filepath.is_dir():
        # Trouver PR_OPERATION_DATA_TABLE.tsv
        tsv_file = filepath / "PR_OPERATION_DATA_TABLE.tsv"
        if not tsv_file.exists():
            tsv_file = filepath / "PR_OPERATION.tsv"
        if tsv_file.exists():
            log.info('Chargement du mapping factures->polices depuis %s ...', tsv_file.name)
            try:
                with open(tsv_file, 'r', encoding=ENCODING, errors='replace') as f:
                    lines = f.readlines()
                    if lines:
                        headers = [p.strip().strip('"') for p in lines[0].rstrip('\n\r').split(SEPARATOR)]
                        try:
                            num_pol_idx = headers.index('NUM_POLICE')
                            ann_p_idx = headers.index('ANNEE_FACT_PRIME')
                            num_p_idx = headers.index('NUM_FACTURE_PRIME')
                            ann_h_idx = headers.index('ANNEE_FACT_HON')
                            num_h_idx = headers.index('NUM_FACTURE_HON')
                        except ValueError:
                            return mapping

                        for line in lines[1:]:
                            parts = [p.strip().strip('"') for p in line.rstrip('\n\r').split(SEPARATOR)]
                            if len(parts) <= max(num_pol_idx, ann_p_idx, num_p_idx, ann_h_idx, num_h_idx):
                                continue
                            num_pol = parts[num_pol_idx]
                            if not num_pol:
                                continue
                            
                            ann_p = parts[ann_p_idx]
                            num_p = parts[num_p_idx]
                            if ann_p and num_p:
                                mapping[f'{ann_p}|{num_p}'] = num_pol

                            ann_h = parts[ann_h_idx]
                            num_h = parts[num_h_idx]
                            if ann_h and num_h:
                                mapping[f'{ann_h}|{num_h}'] = num_pol
            except Exception as exc:
                log.error('Erreur de lecture du mapping opérations : %s', exc)
    else:
        log.info('Chargement du mapping factures->polices depuis le bloc PR_OPERATION de %s ...', filepath.name)
        try:
            with open(filepath, 'r', encoding=ENCODING, errors='replace') as f:
                in_block = False
                headers = []
                for line in f:
                    line = line.rstrip('\n\r')
                    parts = [p.strip().strip('"') for p in line.split(SEPARATOR)]
                    if not any(parts):
                        continue
                    
                    if not in_block:
                        if 'NUM_OPERATION' in parts and 'NUM_POLICE' in parts and 'ANNEE_FACT_PRIME' in parts:
                            in_block = True
                            headers = parts
                            try:
                                num_pol_idx = headers.index('NUM_POLICE')
                                ann_p_idx = headers.index('ANNEE_FACT_PRIME')
                                num_p_idx = headers.index('NUM_FACTURE_PRIME')
                                ann_h_idx = headers.index('ANNEE_FACT_HON')
                                num_h_idx = headers.index('NUM_FACTURE_HON')
                            except ValueError:
                                in_block = False
                            continue
                    else:
                        upper_cnt = sum(
                            1 for p in parts
                            if p == p.upper() and re.match(r'^[A-Z][A-Z0-9_]*$', p) and len(p) > 1
                        )
                        if upper_cnt >= len(parts) * 0.6 and len(parts) >= 2 and 'NUM_OPERATION' not in parts:
                            break
                        
                        if len(parts) <= max(num_pol_idx, ann_p_idx, num_p_idx, ann_h_idx, num_h_idx):
                            continue
                        num_pol = parts[num_pol_idx]
                        if not num_pol:
                            continue
                        
                        ann_p = parts[ann_p_idx]
                        num_p = parts[num_p_idx]
                        if ann_p and num_p:
                            mapping[f'{ann_p}|{num_p}'] = num_pol

                        ann_h = parts[ann_h_idx]
                        num_h = parts[num_h_idx]
                        if ann_h and num_h:
                            mapping[f'{ann_h}|{num_h}'] = num_pol
        except Exception as exc:
            log.error('Erreur de lecture du bloc PR_OPERATION : %s', exc)
            
    return mapping


class AssurCoreETLv2:

    def __init__(self, odoo: OdooRPC):
        self.odoo = odoo
        self.stats = defaultdict(lambda: {'created': 0, 'updated': 0,
                                           'skipped': 0, 'errors': 0})
        # Caches
        self.client_cache:    dict[str, int] = {}  # NUM_CLIENT → partner.id
        self.facture_key_map: dict[str, int] = {}  # 'ANNEE|NUM' → receipt.id
        self.reg_cache:       dict[str, int] = {}  # NUM_REG_CLT → settlement.id
        self.company_cache:   dict[str, int] = {}  # COMPAGNIE → company.id

    # ── ÉTAPE 1 : Risques ─────────────────────────────────────────────────────

    def import_risks(self, rows: list[dict]) -> None:
        log.info('── ÉTAPE 1 : Risques (%d lignes) ──', len(rows))

        BRANCHE_MAP = {
            'AUTO': 'AUTO', 'AUTOMOBILE': 'AUTO',
            'SANTE': 'SANTE', 'MALADIE': 'SANTE',
            'MRH': 'MRH', 'HABITATION': 'MRH',
            'TRANSPORT': 'TRANSPORT',
            'INCENDIE': 'INCENDIE', 'IRD': 'INCENDIE',
            'VIE': 'VIE', 'ASSISTANCE': 'AUTRE',
            'AVIATIONS': 'AUTRE', 'MARITIME': 'MARITIME',
            'RC': 'RC',
        }

        for row in rows:
            risque  = clean_str(row.get('RISQUE', ''), 50)
            branche_oracle = clean_str(row.get('BRANCHE', ''), 100)
            if not risque or not branche_oracle:
                continue

            # Normaliser la branche
            branche_key = branche_oracle.upper()
            branche = BRANCHE_MAP.get(branche_key, 'AUTRE')
            for k, v in BRANCHE_MAP.items():
                if k in branche_key:
                    branche = v
                    break

            try:
                odoo_id, created = self.odoo.ensure(
                    model='insurance.risk',
                    domain=[('name', '=', risque), ('branche', '=', branche)],
                    create_vals={
                        'name': risque,
                        'branche': branche,
                        'branche_oracle': branche_oracle,
                    },
                )
                if created:
                    self.stats['risks']['created'] += 1
                    log.debug('  Risque créé : %s / %s', risque, branche)
                else:
                    self.stats['risks']['skipped'] += 1
            except Exception as exc:
                self.stats['risks']['errors'] += 1
                log.error('  Risque %s/%s : %s', risque, branche_oracle, exc)

        self._log('risks', 'Risques')

    # ── ÉTAPE 2 : Codes Opérations ────────────────────────────────────────────

    def import_operation_codes(self, rows: list[dict]) -> None:
        """
        Les codes d'opération sont extraits directement depuis les valeurs
        distinctes de CODE_OPERATION1 dans PR_OPERATION (pas une table séparée).
        Cette étape crée les codes manquants dans insurance.operation.code.
        """
        log.info('── ÉTAPE 2 : Codes Opérations (extraits de PR_OPERATION) ──')

        # Mapping connu CODE → (designation, type_normalise)
        KNOWN_CODES = {
            '001': ('Émission initiale', 'EMI'),
            '002': ('Renouvellement', 'REN'),
            '003': ('Avenant de modification', 'AVN'),
            '004': ('Terme / Renouvellement', 'REN'),
            '005': ('Suspension', 'SUS'),
            '006': ('Annulation', 'ANN'),
            '007': ('Résiliation', 'RES'),
            '008': ('Remise en vigueur', 'REM'),
            '009': ('Avenant complémentaire', 'AVN'),
            '100': ('Terme calculé', 'REN'),
            '000': ('Opération divers', 'AUTRE'),
        }

        # Extraire les codes uniques depuis les lignes reçues si disponibles
        unique_codes = set()
        for row in rows:
            for field in ['CODE_OPERATION1', 'CODE_OPERATION2',
                          'CODE_OPERATION3', 'CODE_OPERATION4']:
                code = clean_str(row.get(field, ''), 3)
                if code and code != '000':
                    unique_codes.add(code)

        # Fusionner avec les codes connus
        for code in sorted(KNOWN_CODES.keys()):
            unique_codes.add(code)

        for code in sorted(unique_codes):
            designation, type_op = KNOWN_CODES.get(
                code,
                (f'Opération code {code}', 'AUTRE')
            )
            try:
                _, created = self.odoo.ensure(
                    model='insurance.operation.code',
                    domain=[('code', '=', code)],
                    create_vals={
                        'code': code,
                        'designation': designation,
                        'type_operation': type_op,
                    },
                )
                if created:
                    self.stats['op_codes']['created'] += 1
                    log.debug('  Code opération créé : [%s] %s', code, designation)
                else:
                    self.stats['op_codes']['skipped'] += 1
            except Exception as exc:
                self.stats['op_codes']['errors'] += 1
                log.error('  Code %s : %s', code, exc)

        self._log('op_codes', 'Codes Opérations')

    # ── ÉTAPE 3 : Mise à jour exhaustive des Clients ──────────────────────────

    def update_clients(self, rows: list[dict]) -> None:
        """
        Met à jour les res.partner existants avec les coordonnées complètes
        de PR_CLIENT : CIN, MF, RC, Adresse, Téléphones, Email, Ville.
        Le lien se fait via le champ 'ref' = 'ORA-{NUM_CLIENT}'.
        """
        log.info('── ÉTAPE 3 : Mise à jour clients PR_CLIENT (%d lignes) ──',
                 len(rows))

        # Précharger le cache des partenaires existants
        existing = self.odoo.search_read(
            'res.partner',
            [('ref', 'like', 'ORA-')],
            ['id', 'ref'],
        )
        for r in existing:
            if r['ref'] and r['ref'].startswith('ORA-'):
                self.client_cache[r['ref'][4:]] = r['id']

        batch_updates: list[tuple[int, dict]] = []

        for row in rows:
            num = clean_str(row.get('NUM_CLIENT', ''))
            if not num:
                continue

            partner_id = self.client_cache.get(num)
            if not partner_id:
                # Créer le partenaire s'il n'existe pas encore
                rs = clean_str(row.get('RAISON_SOCIALE', ''), 50) or \
                     f"{clean_str(row.get('PRENOM',''))} {clean_str(row.get('NOM',''))}".strip() or \
                     f'CLIENT-{num}'
                try:
                    partner_id, _ = self.odoo.ensure(
                        'res.partner',
                        [('ref', '=', f'ORA-{num}')],
                        {'name': rs, 'ref': f'ORA-{num}'},
                    )
                    self.client_cache[num] = partner_id
                    self.stats['clients']['created'] += 1
                except Exception as exc:
                    log.error('  Création client ORA-%s : %s', num, exc)
                    self.stats['clients']['errors'] += 1
                    continue

            # Construire les valeurs de mise à jour
            update_vals = {}
            if clean_str(row.get('CIN', ''), 8):
                update_vals['cin'] = clean_str(row['CIN'], 8)
            if clean_str(row.get('MF', ''), 20):
                update_vals['matricule_fiscal'] = clean_str(row['MF'], 20)
            if clean_str(row.get('RC', ''), 20):
                update_vals['registre_commerce'] = clean_str(row['RC'], 20)
            if clean_str(row.get('ADRESSE', ''), 30):
                update_vals['street'] = clean_str(row['ADRESSE'], 30)
            if clean_str(row.get('TEL1', ''), 20):
                update_vals['phone'] = clean_str(row['TEL1'], 20)
            if clean_str(row.get('MOBILE', ''), 20):
                update_vals['mobile'] = clean_str(row['MOBILE'], 20)
            if clean_str(row.get('EMAIL', ''), 30):
                update_vals['email'] = clean_str(row['EMAIL'], 30)
            if row.get('ASSUJETTI', '').upper() in ('O', 'Y', '1'):
                update_vals['assujetti_tva'] = True
            tc = clean_str(row.get('TYPE_CLIENT', ''), 1)
            if tc in ('E', 'P'):
                update_vals['is_company'] = (tc == 'E')

            if update_vals:
                batch_updates.append((partner_id, update_vals))
                self.stats['clients']['updated'] += 1

            # Flush par lots
            if len(batch_updates) >= BATCH_SIZE:
                self._flush_client_updates(batch_updates)
                batch_updates = []

        if batch_updates:
            self._flush_client_updates(batch_updates)

        self._log('clients', 'Clients')

    def _flush_client_updates(self, batch: list[tuple[int, dict]]) -> None:
        for partner_id, vals in batch:
            try:
                self.odoo.batch_write('res.partner', [partner_id], vals)
            except Exception as exc:
                log.error('  Update partenaire %d : %s', partner_id, exc)
                self.stats['clients']['errors'] += 1

    # ── ÉTAPE 4 : Banques ─────────────────────────────────────────────────────

    def import_banks(self, rows: list[dict]) -> None:
        log.info('── ÉTAPE 4 : Banques (%d lignes) ──', len(rows))
        for row in rows:
            banque = clean_str(row.get('BANQUE', ''), 100)
            if not banque:
                continue
            try:
                _, created = self.odoo.ensure(
                    'insurance.bank',
                    [('name', '=', banque)],
                    {'name': banque},
                )
                if created:
                    self.stats['banks']['created'] += 1
                else:
                    self.stats['banks']['skipped'] += 1
            except Exception as exc:
                self.stats['banks']['errors'] += 1
                log.error('  Banque %s : %s', banque, exc)
        self._log('banks', 'Banques')

    # ── ÉTAPE 5 : Factures → insurance.receipt ─────────────────────────────────

    def import_factures(self, rows: list[dict], data_path: Path) -> None:
        """
        Crée les insurance.receipt depuis PR_FACTURE.
        Chaque facture Oracle devient une quittance avec :
          - Référence : ORA-FACT-{ANNEE}-{NUM_FACTURE}
          - Montant   : TOTAL_FACT
          - État      : 'encaissee' si FACTURE_ENCAISSE='O', sinon 'emise'

        Le lien avec la police se fait via :
          1. Le mapping des opérations (via PR_OPERATION) si disponible.
          2. Les polices existantes du client (première police ou unique police).
          3. Une police de fallback dummy si aucune autre police n'est trouvée (requis par Odoo).
        """
        log.info('── ÉTAPE 5 : Factures PR_FACTURE → insurance.receipt (%d) ──',
                 len(rows))

        # Charger le mapping operations->polices
        op_policy_map = load_operation_policy_mapping(data_path)

        # Précharger le cache client
        if not self.client_cache:
            existing = self.odoo.search_read(
                'res.partner', [('ref', 'like', 'ORA-')], ['id', 'ref']
            )
            for r in existing:
                if r.get('ref', '').startswith('ORA-'):
                    self.client_cache[r['ref'][4:]] = r['id']

        # Précharger toutes les polices d'Odoo
        policies_by_num: dict[str, int] = {}
        all_pols = self.odoo.search_read(
            'insurance.policy', [], ['id', 'num_police']
        )
        for p in (all_pols or []):
            policies_by_num[clean_str(p.get('num_police', ''))] = p['id']

        # Précharger les polices existantes par client
        policies_by_client: dict[int, list[int]] = defaultdict(list)
        all_policies = self.odoo.search_read(
            'insurance.policy', [],
            ['id', 'partner_id', 'num_police']
        )
        for p in (all_policies or []):
            pid = p['partner_id'][0] if p.get('partner_id') else None
            if pid:
                policies_by_client[pid].append(p['id'])

        # Créer/Récupérer la police de fallback pour éviter les erreurs not-null
        fallback_policy_id = None
        try:
            partner_id_for_fallback = 1
            partners = self.odoo.search_read('res.partner', [], ['id'], limit=1)
            if partners:
                partner_id_for_fallback = partners[0]['id']
                
            company_id = 1
            companies = self.odoo.search_read('insurance.company', [], ['id'], limit=1)
            if companies:
                company_id = companies[0]['id']

            fallback_policy_id, _ = self.odoo.ensure(
                'insurance.policy',
                [('num_police', '=', 'ORA-POLICY-FALLBACK')],
                {
                    'num_police': 'ORA-POLICY-FALLBACK',
                    'partner_id': partner_id_for_fallback,
                    'company_ins_id': company_id,
                    'state': 'active',
                    'branche': 'AUTRE',
                    'date_effect': date.today().isoformat(),
                    'date_echeance': date.today().replace(year=date.today().year + 1).isoformat(),
                }
            )
        except Exception as exc:
            log.warning("Impossible de créer la police de fallback : %s", exc)

        # Precharger les receipts existants pour idempotence
        existing_receipts = self.odoo.search_read(
            'insurance.receipt',
            [('name', 'like', 'ORA-FACT-')],
            ['id', 'name']
        )
        existing_receipt_names = {r['name']: r['id'] for r in (existing_receipts or [])}

        batch: list[dict] = []

        for row in rows:
            annee   = clean_str(row.get('ANNEE_FACT', ''), 4)
            num     = clean_str(row.get('NUM_FACTURE', ''), 5)
            num_cli = clean_str(row.get('NUM_CLIENT', ''))

            if not annee or not num:
                continue

            receipt_ref = f'ORA-FACT-{annee}-{num}'

            # Idempotence
            if receipt_ref in existing_receipt_names:
                self.facture_key_map[f'{annee}|{num}'] = existing_receipt_names[receipt_ref]
                self.stats['factures']['skipped'] += 1
                continue

            # Résoudre le client
            partner_id = self.client_cache.get(num_cli)

            # Résoudre la police
            policy_id = None
            
            # 1. Essayer le mapping des opérations
            num_police_from_op = op_policy_map.get(f'{annee}|{num}')
            if num_police_from_op:
                policy_id = policies_by_num.get(clean_str(num_police_from_op))
                
            # 2. Si non trouvé, essayer le client avec une seule police ou première police
            if not policy_id and partner_id:
                polices = policies_by_client.get(partner_id, [])
                if polices:
                    policy_id = polices[0]
                    
            # 3. Si toujours non trouvé, utiliser la police de fallback dummy
            if not policy_id:
                policy_id = fallback_policy_id

            total = parse_float(row.get('TOTAL_FACT', '0'))
            total_reg = parse_float(row.get('TOTAL_REG', '0'))
            is_paid = clean_str(row.get('FACTURE_ENCAISSE', 'N'), 1).upper() == 'O'
            date_fact = parse_date(row.get('DATE_FACT', ''))

            state = 'encaissee' if is_paid else ('partielle' if total_reg > 0 else 'emise')
            amount_paid = total_reg if total_reg > 0 else (total if is_paid else 0.0)

            vals = {
                'name': receipt_ref,
                'date_emission': date_fact or date.today().isoformat(),
                'date_echeance': date_fact or date.today().isoformat(),
                'montant_prime': total,
                'amount_total': total,
                'amount_paid': amount_paid,
                'amount_residual': max(0.0, total - amount_paid),
                'state': state,
                'notes': f'Migré depuis PR_FACTURE {annee}/{num}',
                'policy_id': policy_id,
            }
            if partner_id:
                vals['partner_id'] = partner_id  # Ajout si le champ existe sur le modèle

            batch.append(vals)

            if len(batch) >= BATCH_SIZE:
                self._flush_facture_batch(batch, annee, num)
                batch = []

        if batch:
            self._flush_facture_batch(batch, '', '')

        self._log('factures', 'Factures')

    def _flush_facture_batch(self, batch: list[dict], last_annee: str, last_num: str) -> None:
        try:
            new_ids = self.odoo.execute('insurance.receipt', 'create', batch)
            if isinstance(new_ids, int):
                new_ids = [new_ids]
            for vals, new_id in zip(batch, (new_ids or [])):
                # Reconstituer la clé ANNEE|NUM depuis le name ORA-FACT-ANNEE-NUM
                parts = vals['name'].replace('ORA-FACT-', '').split('-')
                if len(parts) >= 2:
                    self.facture_key_map[f'{parts[0]}|{parts[1]}'] = new_id
            self.stats['factures']['created'] += len(new_ids or [])
            log.info('  Batch %d factures créées', len(new_ids or []))
        except Exception as exc:
            self.stats['factures']['errors'] += len(batch)
            log.error('  Batch factures : %s', exc)

    # ── ÉTAPE 6 : Règlements ──────────────────────────────────────────────────

    def import_reglements(self, rows: list[dict]) -> None:
        log.info('── ÉTAPE 6 : Règlements PR_REGELEMENT (%d) ──', len(rows))

        if not self.client_cache:
            existing = self.odoo.search_read(
                'res.partner', [('ref', 'like', 'ORA-')], ['id', 'ref']
            )
            for r in existing:
                if r.get('ref', '').startswith('ORA-'):
                    self.client_cache[r['ref'][4:]] = r['id']

        # Charger les settlements existants
        existing_sett = self.odoo.search_read(
            'insurance.settlement',
            [('name', 'like', 'ORA-REG-')],
            ['id', 'name']
        )
        existing_names = {r['name']: r['id'] for r in (existing_sett or [])}
        self.reg_cache = {r['name'].replace('ORA-REG-', ''): r['id']
                          for r in (existing_sett or [])}

        batch: list[dict] = []

        for row in rows:
            num_reg = clean_str(row.get('NUM_REG_CLT', ''))
            num_cli = clean_str(row.get('NUM_CLIENT', ''))
            if not num_reg:
                continue

            ora_name = f'ORA-REG-{num_reg}'
            if ora_name in existing_names:
                self.reg_cache[num_reg] = existing_names[ora_name]
                self.stats['reglements']['skipped'] += 1
                continue

            partner_id = self.client_cache.get(num_cli)
            montant = parse_float(row.get('MONTANT_REG', '0'))
            date_reg = parse_date(row.get('DATE_REG', '')) or date.today().isoformat()

            TYPE_MAP = {'C': 'C', 'E': 'E', 'V': 'V', 'P': 'P', 'A': 'A'}
            type_reg = TYPE_MAP.get(clean_str(row.get('TYPE_REG', 'C'), 1), 'C')

            STATE_MAP = {'O': 'regle', 'N': 'brouillon'}
            is_paid = clean_str(row.get('REGLE', 'N'), 1)
            is_impaye = clean_str(row.get('IMPAYE', 'N'), 1).upper() == 'O'
            state = 'impaye' if is_impaye else STATE_MAP.get(is_paid.upper(), 'brouillon')

            vals = {
                'name': ora_name,
                'partner_id': partner_id or 1,
                'date_reg': date_reg,
                'type_reg': type_reg,
                'montant_reg': montant,
                'num_cheque': clean_str(row.get('NUM_CHEQUE', ''), 20),
                'state': state,
                'imputer': state == 'regle',
                'notes': f'Migré depuis PR_REGELEMENT {num_reg}',
            }

            batch.append(vals)

            if len(batch) >= BATCH_SIZE:
                self._flush_reglement_batch(batch, num_reg)
                batch = []

        if batch:
            self._flush_reglement_batch(batch, '')

        self._log('reglements', 'Règlements')

    def _flush_reglement_batch(self, batch: list[dict], last_num: str) -> None:
        try:
            new_ids = self.odoo.execute('insurance.settlement', 'create', batch)
            if isinstance(new_ids, int):
                new_ids = [new_ids]
            for vals, new_id in zip(batch, (new_ids or [])):
                num = vals['name'].replace('ORA-REG-', '')
                self.reg_cache[num] = new_id
            self.stats['reglements']['created'] += len(new_ids or [])
            log.info('  Batch %d règlements créés', len(new_ids or []))
        except Exception as exc:
            self.stats['reglements']['errors'] += len(batch)
            log.error('  Batch règlements : %s', exc)

    # ── ÉTAPE 7 : Lettrage PR_REG_FACTURE ────────────────────────────────────

    def import_lettrage(self, rows: list[dict]) -> None:
        """
        Lettrage : lie chaque règlement (NUM_REG_CLT) à sa facture (ANNEE_FACT|NUM_FACTURE).
        Action Odoo :
          - Trouve l'insurance.receipt correspondant à la facture
          - Trouve l'insurance.settlement correspondant au règlement
          - Met à jour receipt_id sur le settlement
          - Marque l'insurance.receipt comme 'encaissee' si montant = total
        """
        log.info('── ÉTAPE 7 : Lettrage PR_REG_FACTURE (%d lignes) ──', len(rows))

        # Grouper par facture pour calculer le total imputé
        facture_imputations: dict[str, float] = defaultdict(float)
        reg_to_facture: list[tuple[str, str]] = []  # (num_reg, facture_key)

        for row in rows:
            num_reg   = clean_str(row.get('NUM_REG_CLT', ''))
            annee     = clean_str(row.get('ANNEE_FACT', ''), 4)
            num_fact  = clean_str(row.get('NUM_FACTURE', ''), 5)
            montant   = parse_float(row.get('MONTANT_REG', '0'))
            supp      = clean_str(row.get('SUPP_LOG', 'N'), 1)

            if not num_reg or not annee or not num_fact or supp == 'O':
                continue

            facture_key = f'{annee}|{num_fact}'
            facture_imputations[facture_key] += montant
            reg_to_facture.append((num_reg, facture_key))

        # 1. Charger les liens existants dans Odoo pour éviter de réécrire ce qui l'est déjà
        existing_links: dict[int, int] = {}
        if self.reg_cache:
            log.info('  Préchargement des liens de lettrage existants depuis Odoo ...')
            all_sett_ids = list(self.reg_cache.values())
            # Par lots de 500 pour éviter de saturer les arguments
            for i in range(0, len(all_sett_ids), 500):
                batch_ids = all_sett_ids[i:i+500]
                recs = self.odoo.search_read(
                    'insurance.settlement',
                    [('id', 'in', batch_ids)],
                    ['id', 'receipt_id']
                )
                for r in (recs or []):
                    curr = r.get('receipt_id')
                    if curr:
                        existing_links[r['id']] = curr[0]

        # 2. Récupérer les données des receipts (montants, états, etc.)
        receipt_data: dict[int, dict] = {}
        if self.facture_key_map:
            log.info('  Préchargement des quittances depuis Odoo ...')
            all_receipt_ids = list(self.facture_key_map.values())
            for i in range(0, len(all_receipt_ids), 200):
                batch_ids = all_receipt_ids[i:i+200]
                recs = self.odoo.search_read(
                    'insurance.receipt',
                    [('id', 'in', batch_ids)],
                    ['id', 'amount_total', 'state', 'amount_paid', 'amount_residual']
                )
                for r in (recs or []):
                    receipt_data[r['id']] = r

        # Appliquer le lettrage
        receipts_to_update: dict[int, dict] = {}

        link_writes = 0
        link_skipped = 0

        # Grouper les règlements par receipt_id pour mise à jour par lots
        settlements_by_receipt = defaultdict(list)

        for num_reg, facture_key in reg_to_facture:
            receipt_id = self.facture_key_map.get(facture_key)
            settlement_id = self.reg_cache.get(num_reg)

            if receipt_id and settlement_id:
                # Vérifier si c'est déjà lié au bon receipt
                if existing_links.get(settlement_id) == receipt_id:
                    link_skipped += 1
                else:
                    settlements_by_receipt[receipt_id].append(settlement_id)

            if receipt_id and receipt_id not in receipts_to_update:
                total_impute = facture_imputations.get(facture_key, 0.0)
                r_data = receipt_data.get(receipt_id, {})
                total_facture = r_data.get('amount_total', 0.0) or 0.0

                # Déterminer le nouvel état
                if total_impute >= total_facture * 0.99:  # 1% tolérance arrondi
                    new_state = 'encaissee'
                    amount_paid = total_facture
                elif total_impute > 0:
                    new_state = 'partielle'
                    amount_paid = total_impute
                else:
                    continue

                # Vérifier si l'état ou le montant payé dans Odoo a besoin d'être mis à jour
                if (r_data.get('state') == new_state and 
                    abs((r_data.get('amount_paid') or 0.0) - amount_paid) < 0.01):
                    continue

                receipts_to_update[receipt_id] = {
                    'state': new_state,
                    'amount_paid': amount_paid,
                    'amount_residual': max(0.0, total_facture - amount_paid),
                }

        # Lier les règlements aux quittances par batches groupés par receipt_id
        for receipt_id, sett_ids in settlements_by_receipt.items():
            try:
                self.odoo.execute(
                    'insurance.settlement', 'write',
                    sett_ids, {'receipt_id': receipt_id, 'imputer': True}
                )
                link_writes += len(sett_ids)
            except Exception:
                pass  # Non bloquant

        log.info('  Liens de règlements : %d mis à jour, %d déjà corrects (ignorés)', link_writes, link_skipped)

        # Appliquer les mises à jour d'état en batch
        encaissees = 0
        partielles = 0
        receipt_writes = 0
        
        # Grouper les quittances par état pour mise à jour globale
        receipts_by_state = defaultdict(list)
        for receipt_id, vals in receipts_to_update.items():
            receipts_by_state[vals['state']].append(receipt_id)

        for state, r_ids in receipts_by_state.items():
            # Par batches de 500 pour optimiser et éviter la surcharge réseau
            for i in range(0, len(r_ids), 500):
                batch_ids = r_ids[i:i+500]
                try:
                    self.odoo.execute('insurance.receipt', 'write', batch_ids, {'state': state})
                    receipt_writes += len(batch_ids)
                    if state == 'encaissee':
                        encaissees += len(batch_ids)
                    else:
                        partielles += len(batch_ids)
                except Exception as exc:
                    log.error('  Erreur mise à jour lettrage batch state=%s : %s', state, exc)
                    self.stats['lettrage']['errors'] += len(batch_ids)

        self.stats['lettrage']['created'] = encaissees
        self.stats['lettrage']['updated'] = partielles
        log.info('  Mise à jour quittances : %d traitées (%d encaissées, %d partielles)', receipt_writes, encaissees, partielles)
        self._log('lettrage', 'Lettrage')

    # ── ÉTAPE 8 : Sinistres (1 ligne) + Expert ────────────────────────────────

    def import_sinistres(self, rows: list[dict]) -> None:
        log.info('── ÉTAPE 8 : Sinistres PR_SINISTRE (%d ligne(s)) ──', len(rows))

        if not self.company_cache:
            companies = self.odoo.search_read(
                'insurance.company', [], ['id', 'name']
            )
            self.company_cache = {r['name']: r['id'] for r in (companies or [])}

        # Précharger les polices
        policies_by_num: dict[str, int] = {}
        all_pols = self.odoo.search_read(
            'insurance.policy', [], ['id', 'num_police']
        )
        for p in (all_pols or []):
            policies_by_num[clean_str(p.get('num_police', ''))] = p['id']

        for row in rows:
            annee   = clean_str(row.get('ANNEE_SIN', ''), 4)
            num_sin = clean_str(row.get('NUM_SINISTRE', ''))
            num_pol = clean_str(row.get('NUM_POLICE', ''), 30)
            if not num_sin:
                continue

            ora_name = f'ORA-SIN-{annee}-{num_sin}'
            existing = self.odoo.execute(
                'insurance.claim', 'search',
                [('name', '=', ora_name)], limit=1
            )
            if existing:
                self.stats['sinistres']['skipped'] += 1
                continue

            policy_id = policies_by_num.get(num_pol)
            if not policy_id:
                log.warning('  Sinistre %s — police %s introuvable', num_sin, num_pol)

            date_sin = parse_date(row.get('DATE_SINISTRE', ''))
            lib_sin = clean_str(row.get('LIB_SINISTRE', ''), 250)
            montant = parse_float(row.get('MONTANT_INDEMNITE', '0'))
            compagnie = clean_str(row.get('COMPAGNIE', ''), 30)
            tiers = clean_str(row.get('TIERS', ''), 50)
            categorie = clean_str(row.get('CATEGORIE_INDEMNISATION', ''), 50)
            ref_sin = clean_str(row.get('REF_SINISTRE', ''), 20)

            try:
                new_id = self.odoo.execute('insurance.claim', 'create', {
                    'name': ora_name,
                    'policy_id': policy_id,
                    'date_sinistre': f'{date_sin} 00:00:00' if date_sin
                                     else f'{date.today().isoformat()} 00:00:00',
                    'date_declaration': date_sin or date.today().isoformat(),
                    'lib_sinistre': lib_sin or f'Sinistre migré depuis Oracle — {num_sin}',
                    'montant_reclame': montant,
                    'montant_indemnite': montant,
                    'categorie_indemnisation': categorie,
                    'tiers': tiers,
                    'ref_compagnie': ref_sin,
                    'state': 'declare',
                    'notes': f'Migré depuis PR_SINISTRE {annee}/{num_sin} | '
                             f'Compagnie: {compagnie}',
                })
                self.stats['sinistres']['created'] += 1
                log.info('  Sinistre %s créé (id=%s)', ora_name, new_id)
            except Exception as exc:
                self.stats['sinistres']['errors'] += 1
                log.error('  Sinistre %s : %s', num_sin, exc)

        self._log('sinistres', 'Sinistres')

    # ── ÉTAPE 9 : Experts ─────────────────────────────────────────────────────

    def import_experts(self, rows: list[dict]) -> None:
        log.info('── ÉTAPE 9 : Experts PR_EXPERT (%d ligne(s)) ──', len(rows))
        for row in rows:
            ref = clean_str(row.get('REF_EXPERT', ''))
            if not ref:
                continue

            ref_ora = f'ORA-EXP-{ref}'
            nom = clean_str(row.get('NOM', ''))
            prenom = clean_str(row.get('PRENOM', ''))
            name = f'{prenom} {nom}'.strip() or f'Expert-{ref}'

            try:
                partner_id, created = self.odoo.ensure(
                    model='res.partner',
                    domain=[('ref', '=', ref_ora)],
                    create_vals={
                        'name': name,
                        'ref': ref_ora,
                        'is_company': False,
                        'is_expert': True,
                        'specialite_expert': 'Auto',
                        'street': clean_str(row.get('ADRESSE', ''), 150),
                        'city': clean_str(row.get('VILLE', ''), 100),
                        'zip': clean_str(row.get('CODE_POST', ''), 20),
                        'phone': clean_str(row.get('TEL1', ''), 30),
                        'mobile': clean_str(row.get('MOBILE', ''), 30),
                        'customer_rank': 0,
                    }
                )
                if created:
                    self.stats['experts']['created'] += 1
                    log.info('  Expert %s créé (id=%s)', name, partner_id)
                else:
                    self.stats['experts']['skipped'] += 1
            except Exception as exc:
                self.stats['experts']['errors'] += 1
                log.error('  Expert %s : %s', name, exc)

        self._log('experts', 'Experts')

    # ── Rapport final ──────────────────────────────────────────────────────────

    def _log(self, key: str, label: str) -> None:
        s = self.stats[key]
        log.info('  %s → créés: %d | màj: %d | ignorés: %d | erreurs: %d',
                 label, s['created'], s['updated'], s['skipped'], s['errors'])

    def print_summary(self) -> None:
        log.info('')
        log.info('══════════════════════════════════════════════')
        log.info('  BILAN FINAL — AssurCore ETL Phase 2')
        log.info('══════════════════════════════════════════════')
        total_created = total_errors = 0
        for step, s in self.stats.items():
            log.info('  %-20s  créés: %5d  màj: %5d  ignorés: %5d  erreurs: %3d',
                     step, s['created'], s['updated'], s['skipped'], s['errors'])
            total_created += s['created']
            total_errors  += s['errors']
        log.info('──────────────────────────────────────────────')
        log.info('  TOTAL créés : %d | Erreurs : %d', total_created, total_errors)
        log.info('══════════════════════════════════════════════')


# ══════════════════════════════════════════════════════════════════════════════
#  ⑦ POINT D'ENTRÉE
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description='AssurCore ETL Phase 2 — Complétion migration Oracle → Odoo'
    )
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument(
        '--steps', default='all',
        help='Étapes : all | risques,codes,clients,banques,factures,reglements,lettrage,sinistres,experts',
    )
    parser.add_argument('--file', default=str(DATA_FILE))
    return parser.parse_args()


def main():
    args = parse_args()
    data_path = Path(args.file)

    log.info('═══════════════════════════════════════════════════')
    log.info('  AssurCore ETL v2 — Phase 2 : Complétion Migration')
    log.info('  Fichier : %s', data_path)
    log.info('  Mode    : %s', 'DRY-RUN' if args.dry_run else 'IMPORT RÉEL')
    log.info('  Étapes  : %s', args.steps)
    log.info('═══════════════════════════════════════════════════')

    if not data_path.exists():
        log.error('Fichier introuvable : %s', data_path)
        sys.exit(1)

    # Parsing
    blocks = parse_data_file_v2(data_path)

    if args.dry_run:
        log.info('[DRY-RUN] Blocs trouvés : %s', list(blocks.keys()))
        log.info('[DRY-RUN] Fin — aucune écriture effectuée.')
        return

    # Connexion Odoo
    odoo = OdooRPC(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD, args.dry_run)
    try:
        odoo.connect(ODOO_USER, ODOO_PASSWORD)
    except Exception as exc:
        log.error('Connexion Odoo impossible : %s', exc)
        sys.exit(1)

    etl = AssurCoreETLv2(odoo)

    steps = [s.strip() for s in args.steps.split(',') if s.strip()] \
            if args.steps != 'all' \
            else ['risques', 'codes', 'clients', 'banques',
                  'factures', 'reglements', 'lettrage', 'sinistres', 'experts']

    if 'risques' in steps:
        etl.import_risks(blocks.get('PR_RISQUE', []))
    if 'codes' in steps:
        etl.import_operation_codes(blocks.get('PR_OPERATION', []))
    if 'clients' in steps:
        etl.update_clients(blocks.get('PR_CLIENT', []))
    if 'banques' in steps:
        etl.import_banks(blocks.get('PR_BANQUE', []))
    if 'factures' in steps:
        etl.import_factures(blocks.get('PR_FACTURE', []), data_path)
    if 'reglements' in steps:
        etl.import_reglements(blocks.get('PR_REGELEMENT', []))
    if 'lettrage' in steps:
        etl.import_lettrage(blocks.get('PR_REG_FACTURE', []))
    if 'sinistres' in steps:
        etl.import_sinistres(blocks.get('PR_SINISTRE', []))
    if 'experts' in steps:
        etl.import_experts(blocks.get('PR_EXPERT', []))

    etl.print_summary()


if __name__ == '__main__':
    main()
