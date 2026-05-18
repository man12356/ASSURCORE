#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  import_assurcore.py — Script ETL Oracle ASSKAREKAMOUN → Odoo 17 AssurCore
================================================================================

Usage :
    python import_assurcore.py [--dry-run] [--steps all|companies|clients|
                                             policies|operations|settlements|claims]

Options :
    --dry-run   Parse et affiche les stats sans écrire dans Odoo
    --steps     Étapes à exécuter (défaut : all)
    --file      Chemin vers DATA_ASS.txt (défaut : ./DATA_ASS.txt)

Étapes d'injection (ordre de dépendance strict) :
    1. companies   : PR_COMPAGNIE    → insurance.company  (référentiel)
    2. clients     : PR_POLICE(*)    → res.partner         (reconstruits depuis les polices)
    3. policies    : PR_POLICE       → insurance.policy
    4. operations  : PR_OPERATION    → insurance.operation
    5. settlements : PR_REGELEMENT   → insurance.settlement
    6. claims      : PR_SINISTRE     → insurance.claim

(*) PR_CLIENT est vide dans ce dump. Les clients sont extraits de RAISON_SOCIALE
    + NUM_CLIENT depuis PR_POLICE, puis dédupliqués.

Idempotence :
    Chaque étape vérifie l'existence du record avant création (via champ ref /
    num_police / name). Relancer le script deux fois ne crée pas de doublons.

Performances :
    Les records sont injectés par lots (BATCH_SIZE). Les IDs sont mis en cache
    localement — aucune requête search XML-RPC en cours de boucle.

Dates (format Oracle) :
    DD/MM/YY  → datetime.date (année 2000+ si YY < 50, 1900+ sinon)
    DD/MM/YYYY → datetime.date

Nombres (locale française) :
    "1 534,069" → 1534.069  (espace milliers + virgule décimale)
================================================================================
"""

import xmlrpc.client
import logging
import sys
print("DEBUG: Running script from", __file__)
import re
import csv
import argparse
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict


# ══════════════════════════════════════════════════════════════════════════════
#  ① CONFIGURATION — À ADAPTER selon votre environnement
# ══════════════════════════════════════════════════════════════════════════════

ODOO_URL      = 'http://localhost:8071'   # URL de l'instance Odoo AssurCore
ODOO_DB       = 'assurcore_db'            # Nom de la base de données Odoo
ODOO_USER     = 'admin'                   # Utilisateur Odoo (doit avoir droits admin)
ODOO_PASSWORD = 'admin'                   # Mot de passe Odoo

DATA_FILE     = Path(__file__).parent.parent / 'DATA_ASS.txt'  # Chemin relatif
ENCODING      = 'utf-8'                   # Encodage du fichier source
SEPARATOR     = '\t'                      # Séparateur (tabulation — détecté empiriquement)
BATCH_SIZE    = 50                        # Nombre de records injectés par appel XML-RPC
LOG_LEVEL     = logging.INFO              # DEBUG pour voir chaque record, INFO pour résumé


# ══════════════════════════════════════════════════════════════════════════════
#  ② LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('import_assurcore.log', encoding='utf-8', mode='a'),
    ],
)
log = logging.getLogger('assurcore.etl')


# ══════════════════════════════════════════════════════════════════════════════
#  ③ SIGNATURES DES BLOCS ORACLE (parseur intelligent)
#
#  Chaque bloc est identifié par un ensemble MINIMUM de colonnes.
#  Dès qu'une ligne d'en-tête contient ces colonnes, le parseur sait
#  dans quelle table il se trouve et commence à accumuler les lignes.
#
#  Priorité : les signatures plus spécifiques sont testées en premier.
#  Blocs sans signature connue → IGNORÉS (bruit AliExpress, EBA_QPOLL…)
# ══════════════════════════════════════════════════════════════════════════════

# (nom_interne, {colonnes_obligatoires_min})
# Les colonnes listées doivent TOUTES être présentes pour identifier le bloc.
TABLE_SIGNATURES = [
    # ── Ordre important : du plus spécifique au moins spécifique ──────────────

    # PR_SINISTRE — très spécifique
    ('PR_SINISTRE', {'ANNEE_SIN', 'NUM_SINISTRE', 'NUM_TEXTE', 'NUM_POLICE', 'DATE_SINISTRE'}),

    # PR_REGELEMENT — règlements clients (chèques)
    ('PR_REGELEMENT', {'NUM_REG_CLT', 'TYPE_CLIENT', 'NUM_CLIENT', 'DATE_REG', 'TYPE_REG', 'MONTANT_REG', 'NUM_CHEQUE'}),

    # PR_OPERATION — opérations / quittances
    ('PR_OPERATION', {'NUM_OPERATION', 'CODE_OPERATION1', 'TYPE_CLIENT', 'NUM_CLIENT', 'NUM_POLICE', 'MONTANT_PRIME', 'COMMISSION'}),

    # PR_POLICE — polices (contient les clients en dénormalisé)
    ('PR_POLICE', {'NUM_POLICE1', 'TYPE_CLIENT', 'NUM_CLIENT', 'ATTRIBUT_CLIENT', 'COMPAGNIE', 'RAISON_SOCIALE'}),

    # PR_CLIENT — table clients (vide dans ce dump, conservée par sécurité)
    ('PR_CLIENT', {'TYPE_CLIENT', 'NUM_CLIENT', 'ATTRIBUT_CLIENT', 'NOM', 'PRENOM', 'RAISON_SOCIALE', 'CIN', 'TEL1'}),

    # PR_COMPAGNIE — référentiel compagnies
    ('PR_COMPAGNIE', {'COMPAGNIE', 'PRIORITE_ENVOI_COMPAGNIE'}),

    # PR_COMMERCIAL — commerciaux
    ('PR_COMMERCIAL', {'NUM_COMMERCIAL', 'COMMERCIAL'}),

    # Blocs à ignorer explicitement (pour éviter les faux positifs)
    # Ces noms commencent par '!' → le parseur les marque comme BRUIT
    ('!AAA_SHIPPING',  {'PRODUIT', 'COUNTRY_NAME', 'TRANSPORTEUR', 'SHIPPING_COST'}),
    ('!EBA_QPOLL',     {'POLL_ID', 'RESPONDENT_ID'}),
    ('!PLT_PLAINTES',  {'PLAINTE_ID', 'CLIENT_ID', 'STATUT_PLAINTE'}),
]

# ══════════════════════════════════════════════════════════════════════════════
#  ④ UTILITAIRES DE CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

def parse_date(value: str) -> str | None:
    """
    Convertit une date Oracle en chaîne ISO 8601 (YYYY-MM-DD).
    Formats reconnus : DD/MM/YY, DD/MM/YYYY, YYYY-MM-DD HH:MM:SS.
    Retourne None si la valeur est vide ou non reconnue.
    """
    if not value or value.strip() in ('', 'NULL', 'null'):
        return None
    v = value.strip()

    # DD/MM/YY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2})$', v)
    if m:
        day, month, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        year = 2000 + yy if yy < 50 else 1900 + yy
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    # DD/MM/YYYY
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', v)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            return None

    # YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', v)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

    log.debug('Date non reconnue : %s', v)
    return None


def parse_float(value: str) -> float:
    """
    Convertit un nombre Oracle (format français) en float Python.
    Gère : "1 534,069" → 1534.069 ; "23,26" → 23.26 ; "300" → 300.0
    Retourne 0.0 si vide ou non parsable.
    """
    if not value or value.strip() in ('', 'NULL', 'null'):
        return 0.0
    v = value.strip().replace('\xa0', '').replace(' ', '')  # espaces insécables
    # Virgule décimale (français)
    if ',' in v and '.' not in v:
        v = v.replace(',', '.')
    elif ',' in v and '.' in v:
        # 1.234,56 → 1234.56
        v = v.replace('.', '').replace(',', '.')
    try:
        return float(v)
    except ValueError:
        log.debug('Float non parsable : %s', value)
        return 0.0


def clean_str(value: str, max_len: int = 0) -> str:
    """Nettoie une chaîne Oracle (strips, gère NULL, tronque)."""
    if not value or value.strip().upper() in ('', 'NULL'):
        return ''
    v = value.strip()
    if max_len and len(v) > max_len:
        v = v[:max_len]
    return v


def oracle_bool(value: str, true_val: str = 'O') -> bool:
    """Convertit CHAR(1) Oracle en booléen Python. 'O'/'Y' → True, 'N' → False."""
    return value.strip().upper() in (true_val.upper(), 'Y', '1', 'TRUE')


# ══════════════════════════════════════════════════════════════════════════════
#  ⑤ PARSEUR INTELLIGENT DU FICHIER DATA_ASS.TXT
# ══════════════════════════════════════════════════════════════════════════════

def identify_block(col_names: list[str]) -> str | None:
    """
    Identifie le bloc Oracle depuis ses noms de colonnes.
    Retourne le nom du bloc ('PR_POLICE', '!AAA_SHIPPING'…) ou None si inconnu.
    """
    col_set = set(col_names)
    for block_name, required in TABLE_SIGNATURES:
        if required.issubset(col_set):
            return block_name
    return None


def is_header_line(parts: list[str]) -> bool:
    """
    Détermine si une ligne est un en-tête Oracle :
    60% des tokens sont des identifiants MAJUSCULES_UNDERSCORE de longueur > 1.
    """
    if len(parts) < 2:
        return False
    upper_cnt = sum(
        1 for p in parts
        if p == p.upper()
        and re.match(r'^[A-Z][A-Z0-9_]*$', p)
        and len(p) > 1
    )
    return upper_cnt >= len(parts) * 0.6


def parse_data_file(filepath: Path) -> dict[str, list[dict]]:
    """
    Lit DATA_ASS.txt ligne par ligne et retourne un dictionnaire :
      { 'PR_POLICE': [{col: val, ...}, ...], 'PR_OPERATION': [...], ... }

    Logique :
      1. Si la ligne ressemble à un en-tête → identifier le bloc
      2. Si le bloc est '!...' ou None → mode BRUIT (ignorer les données)
      3. Sinon → accumuler les lignes dans le bloc correspondant

    Le parseur gère correctement les blocs qui se suivent sans séparateur
    (tel que le fichier Oracle l'exporte).
    """
    blocks: dict[str, list[dict]] = defaultdict(list)
    stats: dict[str, int] = defaultdict(int)

    current_block = None
    current_cols: list[str] = []
    line_count = 0
    ignored_lines = 0

    log.info('Lecture de %s …', filepath)

    with open(filepath, 'r', encoding=ENCODING, errors='replace') as f:
        for lineno, raw_line in enumerate(f, 1):
            line = raw_line.rstrip('\n\r')
            parts = [p.strip().strip('"') for p in line.split(SEPARATOR)]

            # Ignorer les lignes totalement vides
            if not any(parts):
                continue

            if is_header_line(parts):
                # Nouvelle en-tête détectée
                block_name = identify_block(parts)
                current_block = block_name
                current_cols = parts
                if block_name and not block_name.startswith('!'):
                    log.debug('Bloc détecté : %-25s (L%d)  cols=%s',
                              block_name, lineno, parts[:6])
                stats['headers'] += 1
                continue

            # Ligne de données
            if current_block is None or current_block.startswith('!'):
                ignored_lines += 1
                continue

            if len(parts) != len(current_cols):
                # Ligne malformée (colonnes manquantes ou en trop)
                log.debug('L%d — %s : %d colonnes attendues, %d reçues → ignorée',
                          lineno, current_block, len(current_cols), len(parts))
                stats['malformed'] += 1
                continue

            row = dict(zip(current_cols, parts))
            blocks[current_block].append(row)
            line_count += 1

    log.info('Parsing terminé : %d lignes utiles, %d ignorées (bruit/inconnu), %d mal formées',
             line_count, ignored_lines, stats['malformed'])

    for block_name, rows in sorted(blocks.items()):
        log.info('  %-20s : %6d lignes', block_name, len(rows))

    return dict(blocks)


# ══════════════════════════════════════════════════════════════════════════════
#  ⑥ CONNEXION ODOO XML-RPC
# ══════════════════════════════════════════════════════════════════════════════

class OdooRPC:
    """
    Wrapper léger autour de xmlrpc.client pour AssurCore.
    Toutes les opérations passent par execute() pour centraliser
    la gestion d'erreurs et le dry-run.
    """

    def __init__(self, url: str, db: str, user: str, password: str,
                 dry_run: bool = False):
        self.db       = db
        self.password = password
        self.dry_run  = dry_run
        self._uid: int | None = None

        self._common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common',
                                                  allow_none=True)
        self._models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object',
                                                  allow_none=True)

    def connect(self, user: str, password: str) -> int:
        """Authentifie et retourne l'UID Odoo."""
        log.info('Connexion à Odoo (%s / %s) …', ODOO_URL, self.db)
        uid = self._common.authenticate(self.db, user, password, {})
        if not uid:
            raise ConnectionError(
                f'Authentification échouée pour {user}@{self.db}. '
                'Vérifiez ODOO_USER et ODOO_PASSWORD.'
            )
        self._uid = uid
        version = self._common.version()
        log.info('Connecté — UID=%d | Odoo %s', uid, version.get('server_version', '?'))
        return uid

    def execute(self, model: str, method: str, *args, **kwargs):
        """Appel XML-RPC générique. En dry-run, les écritures sont simulées."""
        if self.dry_run and method in ('create', 'write', 'unlink'):
            log.debug('[DRY-RUN] %s.%s(%s)', model, method, args)
            return [] if method == 'create' else True
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, method, list(args), kwargs
        )

    def search_id(self, model: str, domain: list, field: str = 'id') -> int | None:
        """Cherche un seul enregistrement, retourne son ID ou None."""
        ids = self.execute(model, 'search', domain, limit=1)
        return ids[0] if ids else None

    def ensure_record(self, model: str, domain: list,
                      create_vals: dict) -> tuple[int, bool]:
        """
        Retourne (id, created) :
          - Si le record existe → retourne son id, created=False
          - Sinon → le crée et retourne le nouvel id, created=True
        Implémente l'idempotence de base.
        """
        existing = self.execute(model, 'search', domain, limit=1)
        if existing:
            return existing[0], False
        new_id = self.execute(model, 'create', create_vals)
        return new_id, True

    def batch_create(self, model: str, records: list[dict]) -> list[int]:
        """
        Crée des enregistrements par lots de BATCH_SIZE.
        Retourne la liste des IDs créés.
        """
        ids = []
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            if self.dry_run:
                log.debug('[DRY-RUN] batch_create %s × %d', model, len(batch))
                ids.extend(range(99000 + i, 99000 + i + len(batch)))
            else:
                batch_ids = self.execute(model, 'create', batch)
                if isinstance(batch_ids, int):
                    batch_ids = [batch_ids]
                ids.extend(batch_ids or [])
        return ids


# ══════════════════════════════════════════════════════════════════════════════
#  ⑦ ÉTAPES D'INJECTION
# ══════════════════════════════════════════════════════════════════════════════

class AssurCoreETL:
    """
    Orchestre les 6 étapes de migration Oracle → Odoo.

    Caches (dictionnaires Python en mémoire) :
      company_cache  : {nom_compagnie_oracle → odoo_id}
      client_cache   : {num_client_oracle    → odoo_id}
      police_cache   : {num_police_oracle    → odoo_id}
      operation_cache: {num_operation_oracle → odoo_id}
    """

    def __init__(self, odoo: OdooRPC):
        self.odoo = odoo
        self.company_cache:   dict[str, int] = {}
        self.client_cache:    dict[str, int] = {}
        self.police_cache:    dict[str, int] = {}
        self.operation_cache: dict[str, int] = {}
        self.stats: dict[str, dict] = defaultdict(lambda: {'created': 0, 'skipped': 0, 'errors': 0})

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 1 — Compagnies d'assurance
    #  PR_COMPAGNIE → insurance.company
    # ──────────────────────────────────────────────────────────────────────────

    def import_companies(self, rows: list[dict]) -> None:
        """
        Crée les compagnies d'assurance depuis PR_COMPAGNIE.
        Idempotence : recherche par `name` exact.
        """
        log.info('── Étape 1/6 : Compagnies (%d lignes) ──', len(rows))

        for row in rows:
            nom = clean_str(row.get('COMPAGNIE', ''), 30)
            if not nom:
                self.stats['companies']['skipped'] += 1
                continue

            try:
                odoo_id, created = self.odoo.ensure_record(
                    model='insurance.company',
                    domain=[('name', '=', nom)],
                    create_vals={
                        'name': nom,
                        'priorite_envoi': int(row.get('PRIORITE_ENVOI_COMPAGNIE', '0') or 0),
                        'agence_courtier': clean_str(row.get('AGENCE_COURTIER', '')),
                        'active': not oracle_bool(row.get('SUPP_LOG', 'N')),
                    },
                )
                self.company_cache[nom] = odoo_id
                if created:
                    self.stats['companies']['created'] += 1
                    log.info('  ✓ Compagnie créée : %s (id=%d)', nom, odoo_id)
                else:
                    self.stats['companies']['skipped'] += 1
                    log.debug('  ~ Compagnie existante : %s (id=%d)', nom, odoo_id)

            except Exception as exc:
                self.stats['companies']['errors'] += 1
                log.error('  ✗ Compagnie %s : %s', nom, exc)

        # Charger aussi les compagnies déjà existantes dans Odoo
        self._preload_companies()
        self._log_step_stats('companies', 'Compagnies')

    def _preload_companies(self) -> None:
        """Charge toutes les compagnies existantes dans le cache."""
        records = self.odoo.execute('insurance.company', 'search_read',
                                    [], fields=['id', 'name'])
        for r in (records or []):
            self.company_cache[r['name']] = r['id']

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 2 — Clients (res.partner)
    #  Extraits de PR_POLICE (RAISON_SOCIALE + NUM_CLIENT + TYPE_CLIENT)
    #  Note : PR_CLIENT est vide dans ce dump Oracle.
    # ──────────────────────────────────────────────────────────────────────────

    def import_clients_from_policies(self, police_rows: list[dict],
                                     client_rows: list[dict]) -> None:
        """
        Crée les clients res.partner depuis :
          - PR_CLIENT si disponible (NOM, PRENOM, CIN, etc.)
          - Sinon depuis PR_POLICE (RAISON_SOCIALE, NUM_CLIENT dénormalisé)

        Idempotence : le champ `ref` d'Odoo stocke l'ancien NUM_CLIENT Oracle.
        Recherche : domain [('ref', '=', f'ORA-{num_client}')]
        """
        log.info('── Étape 2/6 : Clients ──')

        created_count = 0
        skipped_count = 0
        error_count   = 0

        # ── 2a. Depuis PR_CLIENT (si des données existent) ────────────────────
        if client_rows:
            log.info('  Sous-étape 2a : %d lignes PR_CLIENT', len(client_rows))
            for row in client_rows:
                result = self._upsert_client_from_pr_client(row)
                if result == 'created':   created_count += 1
                elif result == 'skipped': skipped_count += 1
                else:                     error_count   += 1

        # ── 2b. Depuis PR_POLICE (extraction des clients uniques) ─────────────
        # Construire un index NUM_CLIENT → infos dénormalisées
        seen: dict[str, dict] = {}
        for row in police_rows:
            num   = clean_str(row.get('NUM_CLIENT', ''))
            rs    = clean_str(row.get('RAISON_SOCIALE', ''), 50)
            tc    = clean_str(row.get('TYPE_CLIENT', 'P'))
            agence= clean_str(row.get('AGENCE_COURTIER', ''))
            if num and rs and num not in seen:
                seen[num] = {'raison_sociale': rs, 'type_client': tc,
                             'agence': agence, 'num_client': num}

        log.info('  Sous-étape 2b : %d clients uniques extraits de PR_POLICE', len(seen))

        for num, info in seen.items():
            ref = f'ORA-{num}'
            try:
                odoo_id, created = self.odoo.ensure_record(
                    model='res.partner',
                    domain=[('ref', '=', ref)],
                    create_vals=self._build_partner_vals(info, ref),
                )
                self.client_cache[num] = odoo_id
                if created:
                    created_count += 1
                    log.debug('  ✓ Client %s → id=%d (%s)', num, odoo_id,
                              info['raison_sociale'][:30])
                else:
                    skipped_count += 1
                    self.client_cache[num] = odoo_id  # Met en cache même si existant

            except Exception as exc:
                error_count += 1
                log.error('  ✗ Client NUM=%s : %s', num, exc)

        self.stats['clients'] = {'created': created_count, 'skipped': skipped_count,
                                  'errors': error_count}
        self._log_step_stats('clients', 'Clients')

        # Précharger les clients existants non encore en cache
        self._preload_clients()

    def _build_partner_vals(self, info: dict, ref: str) -> dict:
        """Construit le dictionnaire de valeurs pour res.partner."""
        rs = info.get('raison_sociale', '')
        tc = info.get('type_client', 'P')
        is_company = (tc == 'E')

        vals = {
            'name': rs,
            'ref': ref,
            'is_company': is_company,
            'customer_rank': 1,
            'comment': f'Migré depuis Oracle ASSKAREKAMOUN — NUM_CLIENT={info.get("num_client", "")}',
        }
        # Champs supplémentaires si présents dans PR_CLIENT
        if info.get('nom'):
            vals['name'] = f'{info["prenom"]} {info["nom"]}'.strip() if info.get('prenom') else info['nom']
        if info.get('cin'):
            vals['cin'] = clean_str(info['cin'], 8)
        if info.get('mf'):
            vals['matricule_fiscal'] = clean_str(info['mf'], 20)
        if info.get('tel1'):
            vals['phone'] = clean_str(info['tel1'], 20)
        if info.get('mobile'):
            vals['mobile'] = clean_str(info['mobile'], 20)
        if info.get('email'):
            vals['email'] = clean_str(info['email'], 30)
        if info.get('adresse'):
            vals['street'] = clean_str(info['adresse'], 30)
        return vals

    def _upsert_client_from_pr_client(self, row: dict) -> str:
        """Crée ou met à jour un client depuis une ligne PR_CLIENT réelle."""
        num = clean_str(row.get('NUM_CLIENT', ''))
        if not num:
            return 'skipped'

        ref = f'ORA-{num}'
        info = {
            'nom': clean_str(row.get('NOM', ''), 20),
            'prenom': clean_str(row.get('PRENOM', ''), 20),
            'raison_sociale': clean_str(row.get('RAISON_SOCIALE', ''), 50),
            'cin': clean_str(row.get('CIN', ''), 8),
            'mf': clean_str(row.get('MF', ''), 20),
            'tel1': clean_str(row.get('TEL1', ''), 20),
            'mobile': clean_str(row.get('MOBILE', ''), 20),
            'email': clean_str(row.get('EMAIL', ''), 30),
            'adresse': clean_str(row.get('ADRESSE', ''), 30),
            'type_client': clean_str(row.get('TYPE_CLIENT', 'P')),
            'num_client': num,
        }
        # Nom affiché : RS pour entreprise, NOM PRENOM pour particulier
        if not info['raison_sociale']:
            parts = [p for p in [info['prenom'], info['nom']] if p]
            info['raison_sociale'] = ' '.join(parts) or f'CLIENT-{num}'

        try:
            odoo_id, created = self.odoo.ensure_record(
                model='res.partner',
                domain=[('ref', '=', ref)],
                create_vals=self._build_partner_vals(info, ref),
            )
            self.client_cache[num] = odoo_id
            return 'created' if created else 'skipped'
        except Exception as exc:
            log.error('  ✗ PR_CLIENT NUM=%s : %s', num, exc)
            return 'error'

    def _preload_clients(self) -> None:
        """Charge les partners existants (ref ORA-*) dans le cache."""
        records = self.odoo.execute(
            'res.partner', 'search_read',
            [('ref', 'like', 'ORA-')],
            fields=['id', 'ref'],
        )
        for r in (records or []):
            if r.get('ref', '').startswith('ORA-'):
                num = r['ref'][4:]  # Enlever le préfixe 'ORA-'
                self.client_cache[num] = r['id']

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 3 — Polices d'assurance
    #  PR_POLICE → insurance.policy
    # ──────────────────────────────────────────────────────────────────────────

    def import_policies(self, rows: list[dict]) -> None:
        """
        Crée les polices d'assurance depuis PR_POLICE.
        Dépendances : client_cache (étape 2), company_cache (étape 1).
        Idempotence : domain [('num_police', '=', x), ('company_ins_id', '=', y)]
        """
        log.info('── Étape 3/6 : Polices (%d lignes) ──', len(rows))

        # Précharger les polices existantes
        self._preload_policies()

        batch_to_create: list[dict] = []
        batch_ids_map:   list[str]  = []  # pour mettre à jour le cache après create

        for row in rows:
            num_police = clean_str(row.get('NUM_POLICE1', ''), 30)
            compagnie  = clean_str(row.get('COMPAGNIE', ''), 30)
            num_client = clean_str(row.get('NUM_CLIENT', ''))

            if not num_police:
                self.stats['policies']['skipped'] += 1
                continue

            # Idempotence : déjà en cache ?
            cache_key = f'{num_police}|{compagnie}'
            if cache_key in self.police_cache or cache_key in batch_ids_map:
                self.stats['policies']['skipped'] += 1
                continue

            # Résoudre les FKs
            partner_id  = self.client_cache.get(num_client)
            company_id  = self.company_cache.get(compagnie)

            if not partner_id:
                log.warning('  Police %s — client %s introuvable → création partenaire à la volée',
                            num_police, num_client)
                rs = clean_str(row.get('RAISON_SOCIALE', ''), 50) or f'CLIENT-{num_client}'
                try:
                    partner_id, _ = self.odoo.ensure_record(
                        'res.partner',
                        [('ref', '=', f'ORA-{num_client}')],
                        {'name': rs, 'ref': f'ORA-{num_client}', 'customer_rank': 1},
                    )
                    self.client_cache[num_client] = partner_id
                except Exception as exc:
                    log.error('  ✗ Création partenaire à la volée %s : %s', num_client, exc)
                    self.stats['policies']['errors'] += 1
                    continue

            if not company_id:
                log.warning('  Police %s — compagnie "%s" introuvable → creation',
                            num_police, compagnie)
                try:
                    company_id, _ = self.odoo.ensure_record(
                        'insurance.company',
                        [('name', '=', compagnie)],
                        {'name': compagnie},
                    )
                    self.company_cache[compagnie] = company_id
                except Exception as exc:
                    log.error('  ✗ Création compagnie à la volée %s : %s', compagnie, exc)
                    self.stats['policies']['errors'] += 1
                    continue

            vals = {
                'num_police': num_police,
                'partner_id': partner_id,
                'payer_id':   partner_id,   # Payeur = assuré par défaut
                'company_ins_id': company_id,
                'raison_sociale': clean_str(row.get('RAISON_SOCIALE', ''), 50),
                'branche': self._map_branche(row.get('BRANCHE', '')),
                'agence_courtier': clean_str(row.get('AGENCE_COURTIER', ''), 50),
                'type_client': clean_str(row.get('TYPE_CLIENT', 'P')),
                'state': 'active',
                'active': not oracle_bool(row.get('SUPP_LOG', 'N')),
                # Dates : PR_POLICE ne les contient pas directement.
                # Elles seront complétées depuis PR_OPERATION lors de l'étape 4.
                'date_effect':   date.today().isoformat(),
                'date_echeance': date.today().replace(year=date.today().year + 1).isoformat(),
                'notes': clean_str(row.get('NOTES', ''), 250),
            }

            batch_to_create.append(vals)
            batch_ids_map.append(cache_key)

            # Flush du batch
            if len(batch_to_create) >= BATCH_SIZE:
                self._flush_policy_batch(batch_to_create, batch_ids_map, rows)
                batch_to_create = []
                batch_ids_map   = []

        # Flush du dernier batch
        if batch_to_create:
            self._flush_policy_batch(batch_to_create, batch_ids_map, rows)

        self._log_step_stats('policies', 'Polices')

    def _flush_policy_batch(self, batch: list[dict],
                             cache_keys: list[str], rows: list[dict]) -> None:
        """Injecte un batch de polices et met à jour le cache."""
        try:
            new_ids = self.odoo.batch_create('insurance.policy', batch)
            for key, new_id, vals in zip(cache_keys, new_ids, batch):
                self.police_cache[key] = new_id
                # Aussi indexer par num_police seul
                self.police_cache[vals['num_police']] = new_id
            self.stats['policies']['created'] += len(new_ids)
            log.info('  ✓ Batch %d polices créées', len(new_ids))
        except Exception as exc:
            self.stats['policies']['errors'] += len(batch)
            log.error('  ✗ Batch polices : %s', exc)

    def _preload_policies(self) -> None:
        """Charge les polices existantes dans le cache."""
        records = self.odoo.execute(
            'insurance.policy', 'search_read',
            [],
            fields=['id', 'num_police', 'company_ins_id'],
        )
        for r in (records or []):
            cid = r['company_ins_id'][0] if r.get('company_ins_id') else 0
            # Retrouver le nom de la compagnie depuis le cache inversé
            comp_name = next(
                (k for k, v in self.company_cache.items() if v == cid), str(cid)
            )
            key = f'{r["num_police"]}|{comp_name}'
            self.police_cache[key] = r['id']
            self.police_cache[r['num_police']] = r['id']

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 4 — Opérations / Quittances
    #  PR_OPERATION → insurance.operation
    # ──────────────────────────────────────────────────────────────────────────

    def import_operations(self, rows: list[dict]) -> None:
        """
        Crée les opérations (avenants, renouvellements, quittances).
        Dépendances : police_cache (étape 3).
        Idempotence : domain [('name', 'like', 'ORA-OP-{NUM_OPERATION}')]
        """
        log.info('── Étape 4/6 : Opérations (%d lignes) ──', len(rows))

        # Précharger les opérations existantes
        existing = self.odoo.execute(
            'insurance.operation', 'search_read',
            [('name', 'like', 'ORA-OP-')],
            fields=['id', 'name'],
        )
        existing_names = {r['name']: r['id'] for r in (existing or [])}

        batch: list[dict] = []
        batch_keys: list[str] = []

        for row in rows:
            num_op    = clean_str(row.get('NUM_OPERATION', ''))
            num_police= clean_str(row.get('NUM_POLICE', ''), 30)
            code_op   = clean_str(row.get('CODE_OPERATION1', ''), 3)
            date_op   = parse_date(row.get('DATE_OP', ''))
            montant   = parse_float(row.get('MONTANT_PRIME', '0'))
            commission= parse_float(row.get('COMMISSION', '0'))

            if not num_op:
                self.stats['operations']['skipped'] += 1
                continue

            # Référence unique Oracle
            ora_name = f'ORA-OP-{num_op}'

            # Idempotence
            if ora_name in existing_names:
                op_id = existing_names[ora_name]
                self.operation_cache[num_op] = op_id
                try:
                    self.odoo.execute(
                        'insurance.operation', 'write',
                        [op_id],
                        {
                            'annee_fact_prime': int(parse_float(row.get('ANNEE_FACT_PRIME', '0'))),
                            'num_edit_facture_prime': clean_str(row.get('NUM_EDIT_FACTURE_PRIME', ''), 30),
                            'annee_fact_hon': int(parse_float(row.get('ANNEE_FACT_HON', '0'))),
                            'num_edit_facture_hon': clean_str(row.get('NUM_EDIT_FACTURE_HON', ''), 30),
                            'categorie_facture_prime': clean_str(row.get('CATEGORIE_FACTURE_PRIME', ''), 20),
                            'categorie_facture_hon': clean_str(row.get('CATEGORIE_FACTURE_HON', ''), 20),
                            'attribut_client': clean_str(row.get('ATTRIBUT_CLIENT', ''), 50),
                        }
                    )
                    self.stats['operations']['updated'] += 1
                except Exception as exc:
                    log.error('  Erreur de mise à jour op %s : %s', num_op, exc)
                    self.stats['operations']['errors'] += 1
                continue

            # Résolution police
            policy_id = self.police_cache.get(num_police)
            if not policy_id:
                log.warning('  Opération %s — police %s introuvable → ignorée',
                            num_op, num_police)
                self.stats['operations']['skipped'] += 1
                continue

            # Correction des dates incohérentes (Oracle legacy data)
            du = parse_date(row.get('DATE_VALIDITE_DU', ''))
            au = parse_date(row.get('DATE_VALIDITE_AU', ''))
            
            if du and au and au < du:
                log.debug('  Correction date_validite_au (%s) < date_validite_du (%s) pour op %s', au, du, num_op)
                au = du  # On force au moins l'égalité pour l'opération

            vals = {
                'name': ora_name,
                'policy_id': policy_id,
                'code_operation': self._map_code_operation(code_op),
                'date_op': date_op or date.today().isoformat(),
                'date_validite_du': du,
                'date_validite_au': au,
                'num_quittance': clean_str(row.get('NUM_QUITTANCE', ''), 30),
                'num_attestation': clean_str(row.get('NUM_ATTESTATION', ''), 20),
                'vehicule': clean_str(row.get('VEHICULE', ''), 30),
                'montant_prime': montant,
                'commission': commission,
                'montant_honoraire_ht': parse_float(row.get('MONTANT_HONORAIRE_HT', '0')),
                'designation': clean_str(row.get('DESIGNATION', ''), 250),
                'nature': clean_str(row.get('NATURE', 'R'), 1),
                'state': 'confirmed',
                'active': not oracle_bool(row.get('SUPP_LOG', 'N')),
                'annee_fact_prime': int(parse_float(row.get('ANNEE_FACT_PRIME', '0'))),
                'num_edit_facture_prime': clean_str(row.get('NUM_EDIT_FACTURE_PRIME', ''), 30),
                'annee_fact_hon': int(parse_float(row.get('ANNEE_FACT_HON', '0'))),
                'num_edit_facture_hon': clean_str(row.get('NUM_EDIT_FACTURE_HON', ''), 30),
                'categorie_facture_prime': clean_str(row.get('CATEGORIE_FACTURE_PRIME', ''), 20),
                'categorie_facture_hon': clean_str(row.get('CATEGORIE_FACTURE_HON', ''), 20),
                'attribut_client': clean_str(row.get('ATTRIBUT_CLIENT', ''), 50),
            }

            # Mise à jour des dates de la police depuis la première opération
            # NOTE : La police exige echeance > effect (STRICT)
            if du and au and policy_id:
                if au <= du:
                    # On ajoute 1 jour pour respecter la contrainte de la police
                    try:
                        dt_du = date.fromisoformat(du)
                        au = (dt_du + relativedelta(days=1)).isoformat()
                    except:
                        pass
                try:
                    self.odoo.execute('insurance.policy', 'write', [policy_id], {
                        'date_effect': du,
                        'date_echeance': au,
                    })
                except Exception as exc:
                    log.debug('  Echec mise à jour dates police %s : %s', policy_id, exc)

            batch.append(vals)
            batch_keys.append(num_op)

            if len(batch) >= BATCH_SIZE:
                self._flush_operation_batch(batch, batch_keys, existing_names)
                batch      = []
                batch_keys = []

        if batch:
            self._flush_operation_batch(batch, batch_keys, existing_names)

        self._log_step_stats('operations', 'Opérations')

    def _flush_operation_batch(self, batch: list[dict], keys: list[str],
                                existing: dict) -> None:
        try:
            new_ids = self.odoo.batch_create('insurance.operation', batch)
            for num_op, new_id in zip(keys, new_ids):
                self.operation_cache[num_op] = new_id
            self.stats['operations']['created'] += len(new_ids)
            log.info('  ✓ Batch %d opérations créées', len(new_ids))
        except Exception as exc:
            self.stats['operations']['errors'] += len(batch)
            log.error('  ✗ Batch opérations : %s', exc)

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 5 — Règlements clients
    #  PR_REGELEMENT → insurance.settlement
    # ──────────────────────────────────────────────────────────────────────────

    def import_settlements(self, rows: list[dict]) -> None:
        """
        Crée les règlements (chèques, espèces, virements) depuis PR_REGELEMENT.
        Dépendances : client_cache (étape 2).
        Idempotence : domain [('name', '=', 'ORA-REG-{NUM_REG_CLT}')]
        """
        log.info('── Étape 5/6 : Règlements (%d lignes) ──', len(rows))

        # Précharger les règlements existants
        existing = self.odoo.execute(
            'insurance.settlement', 'search_read',
            [('name', 'like', 'ORA-REG-')],
            fields=['id', 'name'],
        )
        existing_names = {r['name']: r['id'] for r in (existing or [])}

        TYPE_REG_MAP = {
            'C': 'C',   # Chèque
            'E': 'E',   # Espèces
            'V': 'V',   # Virement
            'P': 'P',   # Prélèvement
            'A': 'A',   # Avoir
        }

        STATE_MAP = {
            'N': 'brouillon',   # Non imputé
            'O': 'regle',       # Imputé = réglé
        }

        batch: list[dict] = []

        for row in rows:
            num_reg    = clean_str(row.get('NUM_REG_CLT', ''))
            num_client = clean_str(row.get('NUM_CLIENT', ''))

            if not num_reg:
                self.stats['settlements']['skipped'] += 1
                continue

            ora_name = f'ORA-REG-{num_reg}'
            if ora_name in existing_names:
                self.stats['settlements']['skipped'] += 1
                continue

            partner_id = self.client_cache.get(num_client)
            if not partner_id:
                # Règlement orphelin (client non trouvé) → on crée quand même
                # avec un partenaire générique pour ne pas perdre les données
                log.warning('  Règlement %s — client %s introuvable → créé sans lien',
                            num_reg, num_client)

            # Chercher la quittance liée si possible (via NUM_OPERATION)
            num_op    = clean_str(row.get('NUM_OPERATION', ''))
            receipt_id = None
            if num_op:
                op_id = self.operation_cache.get(num_op)
                if op_id:
                    # Chercher la quittance liée à cette opération
                    op_data = self.odoo.execute('insurance.operation', 'read',
                                                [op_id], fields=['receipt_id'])
                    if op_data and op_data[0].get('receipt_id'):
                        receipt_id = op_data[0]['receipt_id'][0]

            imputer = oracle_bool(row.get('IMPUTER', 'N'))
            state   = STATE_MAP.get(
                clean_str(row.get('ENCAISSE', 'N'), 1), 'brouillon'
            )
            if oracle_bool(row.get('IMPAYE', 'N')):
                state = 'impaye'

            vals = {
                'name': ora_name,
                'partner_id': partner_id or 1,  # Fallback partenaire générique
                'date_reg': parse_date(row.get('DATE_REG', '')) or date.today().isoformat(),
                'date_echeance_cheque': parse_date(row.get('DATE_ECHEANCE', '')),
                'type_reg': TYPE_REG_MAP.get(
                    clean_str(row.get('TYPE_REG', 'C'), 1), 'C'
                ),
                'montant_reg': parse_float(row.get('MONTANT_REG', '0')),
                'montant_restant': parse_float(row.get('MONTANT_RESTANT', '0')),
                'num_cheque': clean_str(row.get('NUM_CHEQUE', ''), 20),
                'cin_tireur': clean_str(row.get('CIN_TIREUR', ''), 8),
                'state': state,
                'imputer': imputer,
                'remis_chez': clean_str(row.get('REMIS_CHEZ', ''), 100),
                'notes': clean_str(row.get('NOTES', ''), 250),
            }
            if receipt_id:
                vals['receipt_id'] = receipt_id

            batch.append(vals)

            if len(batch) >= BATCH_SIZE:
                self._flush_settlement_batch(batch)
                batch = []

        if batch:
            self._flush_settlement_batch(batch)

        self._log_step_stats('settlements', 'Règlements')

    def _flush_settlement_batch(self, batch: list[dict]) -> None:
        try:
            new_ids = self.odoo.batch_create('insurance.settlement', batch)
            self.stats['settlements']['created'] += len(new_ids)
            log.info('  ✓ Batch %d règlements créés', len(new_ids))
        except Exception as exc:
            self.stats['settlements']['errors'] += len(batch)
            log.error('  ✗ Batch règlements : %s', exc)

    # ──────────────────────────────────────────────────────────────────────────
    #  ÉTAPE 6 — Sinistres
    #  PR_SINISTRE → insurance.claim
    # ──────────────────────────────────────────────────────────────────────────

    def import_claims(self, rows: list[dict]) -> None:
        """
        Crée les sinistres depuis PR_SINISTRE.
        Dépendances : police_cache (étape 3).
        Idempotence : domain [('name', '=', 'ORA-SIN-{ANNEE}-{NUM_SINISTRE}')]
        """
        log.info('── Étape 6/6 : Sinistres (%d lignes) ──', len(rows))

        for row in rows:
            annee   = clean_str(row.get('ANNEE_SIN', ''))
            num_sin = clean_str(row.get('NUM_SINISTRE', ''))
            num_pol = clean_str(row.get('NUM_POLICE', ''), 30)

            if not num_sin:
                self.stats['claims']['skipped'] += 1
                continue

            ora_name = f'ORA-SIN-{annee}-{num_sin}'

            existing = self.odoo.execute(
                'insurance.claim', 'search',
                [('name', '=', ora_name)], limit=1
            )
            if existing:
                self.stats['claims']['skipped'] += 1
                continue

            policy_id = self.police_cache.get(num_pol)
            if not policy_id:
                log.warning('  Sinistre %s — police %s introuvable → ignoré', num_sin, num_pol)
                self.stats['claims']['skipped'] += 1
                continue

            date_sin = parse_date(row.get('DATE_SINISTRE', ''))

            try:
                new_id = self.odoo.execute('insurance.claim', 'create', {
                    'name': ora_name,
                    'policy_id': policy_id,
                    'date_sinistre': f'{date_sin} 00:00:00' if date_sin else datetime.now().isoformat(sep=' ', timespec='seconds'),
                    'date_declaration': date_sin or date.today().isoformat(),
                    'lib_sinistre': clean_str(row.get('LIB_SINISTRE', ''), 250),
                    'categorie_indemnisation': clean_str(row.get('CATEGORIE_INDEMNISATION', ''), 50),
                    'montant_reclame': parse_float(row.get('MONTANT_INDEMNITE', '0')),
                    'montant_indemnite': parse_float(row.get('MONTANT_INDEMNITE', '0')),
                    'compagnie_ref': clean_str(row.get('COMPAGNIE', ''), 30),
                    'tiers': clean_str(row.get('TIERS', ''), 50),
                    'state': 'declare',
                    'notes': clean_str(row.get('NOTES', ''), 250),
                })
                self.stats['claims']['created'] += 1
                log.info('  ✓ Sinistre %s créé (id=%d)', ora_name, new_id)
            except Exception as exc:
                self.stats['claims']['errors'] += 1
                log.error('  ✗ Sinistre %s : %s', ora_name, exc)

        self._log_step_stats('claims', 'Sinistres')

    # ──────────────────────────────────────────────────────────────────────────
    #  Utilitaires de mapping métier
    # ──────────────────────────────────────────────────────────────────────────

    # Mapping codes opération Oracle (3 chiffres) → selection AssurCore
    _CODE_OP_MAP: dict[str, str] = {
        '001': 'EMI',   # Émission initiale
        '002': 'REN',   # Renouvellement
        '003': 'AVN',   # Avenant
        '004': 'REN',   # Renouvellement (variante)
        '005': 'SUS',   # Suspension
        '006': 'ANN',   # Annulation
        '007': 'RES',   # Résiliation
        '008': 'REM',   # Remise en vigueur
        '009': 'AVN',   # Avenant (autre code)
        '100': 'REN',   # Terme
    }

    # Mapping branches Oracle → selection AssurCore
    _BRANCHE_MAP: dict[str, str] = {
        'AUTO':       'AUTO',
        'AUTOMOBILE': 'AUTO',
        'VEH':        'AUTO',
        'MALADIE':    'SANTE',
        'SANTE':      'SANTE',
        'SANTÉ':      'SANTE',
        'MRH':        'MRH',
        'HABITATION': 'MRH',
        'TRANSPORT':  'TRANSPORT',
        'INCENDIE':   'INCENDIE',
        'IRD':        'INCENDIE',
        'VIE':        'VIE',
        'RC':         'RC',
        'RCP':        'RC',
        'MARITIME':   'MARITIME',
        'MAR':        'MARITIME',
    }

    def _map_code_operation(self, code: str) -> str:
        code = code.strip().lstrip('0').zfill(3)
        return self._CODE_OP_MAP.get(code, 'REN')

    def _map_branche(self, branche: str) -> str:
        b = branche.strip().upper()
        return self._BRANCHE_MAP.get(b, 'AUTRE')

    # ──────────────────────────────────────────────────────────────────────────
    #  Rapport final
    # ──────────────────────────────────────────────────────────────────────────

    def _log_step_stats(self, key: str, label: str) -> None:
        s = self.stats[key]
        log.info('  %s → créés: %d | existants/ignorés: %d | erreurs: %d',
                 label, s['created'], s['skipped'], s['errors'])

    def print_summary(self) -> None:
        log.info('')
        log.info('══════════════════════════════════════════')
        log.info('  RÉSUMÉ FINAL — Migration AssurCore')
        log.info('══════════════════════════════════════════')
        total_created = total_errors = 0
        for step, s in self.stats.items():
            log.info('  %-15s  créés: %5d  ignorés: %5d  erreurs: %3d',
                     step, s['created'], s['skipped'], s['errors'])
            total_created += s['created']
            total_errors  += s['errors']
        log.info('──────────────────────────────────────────')
        log.info('  TOTAL créés : %d | Erreurs : %d', total_created, total_errors)
        log.info('══════════════════════════════════════════')


# ══════════════════════════════════════════════════════════════════════════════
#  ⑧ POINT D'ENTRÉE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='ETL Oracle ASSKAREKAMOUN → Odoo AssurCore'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Parse et analyse sans écrire dans Odoo',
    )
    parser.add_argument(
        '--steps', default='all',
        help='Étapes à exécuter : all | companies,clients,policies,operations,settlements,claims',
    )
    parser.add_argument(
        '--file', default=str(DATA_FILE),
        help=f'Chemin vers DATA_ASS.txt (défaut : {DATA_FILE})',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_path = Path(args.file)

    log.info('═══════════════════════════════════════════════════════')
    log.info('  AssurCore ETL — Oracle ASSKAREKAMOUN → Odoo 17')
    log.info('  Fichier : %s', data_path)
    log.info('  Mode    : %s', 'DRY-RUN (aucune écriture)' if args.dry_run else 'IMPORT RÉEL')
    log.info('  Étapes  : %s', args.steps)
    log.info('═══════════════════════════════════════════════════════')

    # ── Vérification du fichier ────────────────────────────────────────────────
    if not data_path.exists():
        log.error('Fichier introuvable : %s', data_path)
        sys.exit(1)

    # ── Parsing du fichier ────────────────────────────────────────────────────
    blocks = parse_data_file(data_path)

    if args.dry_run:
        log.info('[DRY-RUN] Parsing terminé. Aucune écriture dans Odoo.')
        log.info('Blocs disponibles : %s', list(blocks.keys()))
        return

    # ── Connexion Odoo ────────────────────────────────────────────────────────
    odoo = OdooRPC(
        url=ODOO_URL, db=ODOO_DB,
        user=ODOO_USER, password=ODOO_PASSWORD,
        dry_run=args.dry_run,
    )
    try:
        odoo.connect(ODOO_USER, ODOO_PASSWORD)
    except Exception as exc:
        log.error('Impossible de se connecter à Odoo : %s', exc)
        log.error('Vérifiez ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD en haut du script.')
        sys.exit(1)

    etl = AssurCoreETL(odoo)

    # ── Sélection des étapes ──────────────────────────────────────────────────
    steps = args.steps.lower().split(',') if args.steps != 'all' else [
        'companies', 'clients', 'policies', 'operations', 'settlements', 'claims'
    ]
    steps = [s.strip() for s in steps]

    # ── Exécution des étapes dans l'ordre de dépendance ─────────────────────
    if 'companies' in steps:
        etl.import_companies(blocks.get('PR_COMPAGNIE', []))

    if 'clients' in steps:
        etl.import_clients_from_policies(
            police_rows=blocks.get('PR_POLICE', []),
            client_rows=blocks.get('PR_CLIENT', []),
        )

    if 'policies' in steps:
        # S'assurer que les caches sont chargés même si on saute une étape
        if not etl.company_cache:
            etl._preload_companies()
        if not etl.client_cache:
            etl._preload_clients()
        etl.import_policies(blocks.get('PR_POLICE', []))

    if 'operations' in steps:
        if not etl.police_cache:
            etl._preload_policies()
        etl.import_operations(blocks.get('PR_OPERATION', []))

    if 'settlements' in steps:
        if not etl.client_cache:
            etl._preload_clients()
        etl.import_settlements(blocks.get('PR_REGELEMENT', []))

    if 'claims' in steps:
        if not etl.police_cache:
            etl._preload_policies()
        etl.import_claims(blocks.get('PR_SINISTRE', []))

    # ── Résumé ────────────────────────────────────────────────────────────────
    etl.print_summary()


if __name__ == '__main__':
    main()
