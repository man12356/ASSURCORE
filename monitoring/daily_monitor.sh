#!/bin/bash
# ==============================================================================
#  daily_monitor.sh — Moniteur Quotidien AssurCore VPS
#  Genere un rapport complet dans /tmp/monitoring/YYYY-MM-DD.txt
#
#  Sections :
#    1. Sécurité SSH    — attaques, IPs suspectes, tentatives bruteforce
#    2. Sécurité Systeme — utilisateurs, sudo, fichiers sensibles
#    3. Stockage        — disque, volumes Docker, PostgreSQL
#    4. Réseau          — ports ouverts, connexions actives
#    5. Docker          — santé des containers, logs d'erreurs
#    6. Odoo/PostgreSQL — santé applicative, taille base
#    7. Ressources      — CPU, RAM, charge
#    8. Résumé + Score  — niveau de risque global (OK/WARN/CRITICAL)
#
#  Usage :
#    chmod +x daily_monitor.sh
#    ./daily_monitor.sh
#    # Cron quotidien : 0 6 * * * /root/assurcore_prod/monitoring/daily_monitor.sh
# ==============================================================================

# set -euo pipefail  # Desactive — grep retourne 1 quand pas de resultat, ce qui stopperait le script

# ── Configuration ──────────────────────────────────────────────────────────────
REPORT_DIR="/tmp/monitoring"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
REPORT="$REPORT_DIR/$DATE.txt"
DB_NAME="assurcore_db"
DB_USER="odoo"
ODOO_PORT="8071"
MAX_DISK_PCT=80        # Seuil alerte disque (%)
MAX_RAM_PCT=85         # Seuil alerte RAM (%)
MAX_SSH_FAILURES=20    # Seuil alerte tentatives SSH/jour

# ── Compteurs risque ────────────────────────────────────────────────────────────
WARNINGS=0
CRITICALS=0

# ── Helpers ────────────────────────────────────────────────────────────────────
mkdir -p "$REPORT_DIR"

section()  { echo "" >> "$REPORT"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT"; echo "  $1" >> "$REPORT"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$REPORT"; }
ok()       { echo "  [OK]      $1" >> "$REPORT"; }
warn()     { echo "  [WARN]    $1" >> "$REPORT"; WARNINGS=$((WARNINGS+1)); }
critical() { echo "  [CRIT]    $1" >> "$REPORT"; CRITICALS=$((CRITICALS+1)); }
info()     { echo "  [INFO]    $1" >> "$REPORT"; }
raw()      { echo "$1" >> "$REPORT"; }

# ── En-tete du rapport ─────────────────────────────────────────────────────────
cat > "$REPORT" << HEADER
╔══════════════════════════════════════════════════════════════╗
║         RAPPORT MONITORING ASSURCORE — $DATE          ║
║         Genere le $DATE à $TIME                   ║
╚══════════════════════════════════════════════════════════════╝
Serveur   : $(hostname)
IP        : $(hostname -I | awk '{print $1}')
OS        : $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)
Kernel    : $(uname -r)
Uptime    : $(uptime -p 2>/dev/null || uptime)
HEADER

# ══════════════════════════════════════════════════════════════════════════════
#  1. SÉCURITÉ SSH
# ══════════════════════════════════════════════════════════════════════════════
section "1. SÉCURITÉ SSH"

# Tentatives de connexion échouées aujourd'hui
SSH_FAILURES=$(grep "$(date '+%b %e')" /var/log/secure 2>/dev/null | grep -c "Failed password" || \
              grep "$(date '+%b %e')" /var/log/auth.log 2>/dev/null | grep -c "Failed password" || echo "0")

info "Tentatives SSH échouées aujourd'hui : $SSH_FAILURES"

if [ "$SSH_FAILURES" -gt 100 ]; then
    critical "ATTAQUE BRUTEFORCE ACTIVE : $SSH_FAILURES tentatives aujourd'hui !"
elif [ "$SSH_FAILURES" -gt "$MAX_SSH_FAILURES" ]; then
    warn "Nombreuses tentatives SSH : $SSH_FAILURES (seuil=$MAX_SSH_FAILURES)"
else
    ok "Tentatives SSH dans les limites normales"
fi

# Top 10 IPs attaquantes
raw ""
raw "  Top IPs suspectes (dernières 24h) :"
grep "Failed password" /var/log/secure 2>/dev/null | \
    grep "$(date '+%b %e')" | \
    awk '{print $11}' | sort | uniq -c | sort -rn | head -10 | \
    while read count ip; do
        echo "    $count tentatives depuis $ip" >> "$REPORT"
    done

# Connexions SSH actives
ACTIVE_SSH=$(who | grep -c "pts" || echo "0")
info "Sessions SSH actives : $ACTIVE_SSH"
if [ "$ACTIVE_SSH" -gt 5 ]; then
    warn "Nombreuses sessions SSH ouvertes : $ACTIVE_SSH"
fi

# Dernières connexions réussies
raw ""
raw "  Dernières connexions réussies :"
last | head -5 | while read line; do
    echo "    $line" >> "$REPORT"
done

# Vérifier si root login SSH est autorisé
ROOT_LOGIN=$(grep -E "^PermitRootLogin" /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo "yes")
if [ "$ROOT_LOGIN" = "yes" ] || [ -z "$ROOT_LOGIN" ]; then
    warn "PermitRootLogin=yes — connexion root SSH autorisée (risque élevé)"
else
    ok "PermitRootLogin désactivé"
fi

# Port SSH
SSH_PORT=$(grep -E "^Port " /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' || echo "22")
if [ "$SSH_PORT" = "22" ]; then
    warn "SSH sur port standard 22 — cible des scanners automatiques"
else
    ok "SSH sur port non-standard : $SSH_PORT"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  2. SÉCURITÉ SYSTÈME
# ══════════════════════════════════════════════════════════════════════════════
section "2. SÉCURITÉ SYSTÈME"

# Utilisateurs avec UID 0 (root)
ROOT_USERS=$(awk -F: '$3==0 {print $1}' /etc/passwd | tr '\n' ' ')
info "Utilisateurs UID=0 : $ROOT_USERS"
ROOT_COUNT=$(echo "$ROOT_USERS" | wc -w)
if [ "$ROOT_COUNT" -gt 1 ]; then
    critical "Plusieurs comptes root détectés : $ROOT_USERS"
else
    ok "Un seul compte root"
fi

# Vérifier les mises à jour de sécurité disponibles
UPDATES=$(yum check-update --security 2>/dev/null | grep -c "^" || echo "N/A")
if [ "$UPDATES" != "N/A" ] && [ "$UPDATES" -gt 1 ]; then
    warn "$UPDATES mises à jour de sécurité disponibles"
else
    ok "Système à jour (ou vérification non disponible)"
fi

# Processus suspects (miners crypto, etc.)
SUSPICIOUS=$(ps aux | grep -E "xmrig|minerd|cryptonight|cpuminer|kworker.*\[" | grep -v grep | wc -l)
if [ "$SUSPICIOUS" -gt 0 ]; then
    critical "Processus suspects détectés (potentiel miner crypto) !"
    ps aux | grep -E "xmrig|minerd|cryptonight|cpuminer" | grep -v grep >> "$REPORT"
else
    ok "Aucun processus suspect détecté"
fi

# Connexions réseau sortantes suspectes
OUTBOUND=$(ss -tnp 2>/dev/null | grep ESTABLISHED | awk '{print $5}' | \
           grep -vE ":(443|80|5432|8069|8071|22|53)" | head -10)
if [ -n "$OUTBOUND" ]; then
    warn "Connexions sortantes sur ports non standards :"
    echo "$OUTBOUND" | while read line; do echo "    $line" >> "$REPORT"; done
else
    ok "Aucune connexion sortante suspecte"
fi

# Fichiers SUID récemment modifiés
SUID_RECENT=$(find /usr /bin /sbin -perm /4000 -newer /etc/passwd 2>/dev/null | head -5)
if [ -n "$SUID_RECENT" ]; then
    warn "Fichiers SUID modifiés récemment : $SUID_RECENT"
else
    ok "Aucun fichier SUID modifié récemment"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  3. STOCKAGE
# ══════════════════════════════════════════════════════════════════════════════
section "3. STOCKAGE"

# Disque système
raw ""
raw "  Utilisation des partitions :"
df -h | grep -E "^/|Filesystem" | while read line; do
    echo "    $line" >> "$REPORT"
    PCT=$(echo "$line" | awk '{print $5}' | tr -d '%' 2>/dev/null || echo "0")
    if echo "$PCT" | grep -qE '^[0-9]+$'; then
        if [ "$PCT" -gt 90 ]; then
            critical "Partition critique : $line"
        elif [ "$PCT" -gt "$MAX_DISK_PCT" ]; then
            warn "Partition presque pleine : $line"
        fi
    fi
done

# Volumes Docker
raw ""
raw "  Volumes Docker :"
docker system df 2>/dev/null | while read line; do
    echo "    $line" >> "$REPORT"
done

# Taille de la base PostgreSQL
PG_SIZE=$(docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db -t \
    -c "SELECT pg_size_pretty(pg_database_size('assurcore_db'));" 2>/dev/null | tr -d ' ')
info "Taille base assurcore_db : ${PG_SIZE:-N/A}"

# Taille des tables principales
raw ""
raw "  Top 5 tables par taille :"
docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db 2>/dev/null << 'SQL' | while read line; do echo "    $line" >> "$REPORT"; done
SELECT
    relname AS table,
    pg_size_pretty(pg_total_relation_size(oid)) AS taille
FROM pg_class
WHERE relkind = 'r' AND relname NOT LIKE 'pg_%'
ORDER BY pg_total_relation_size(oid) DESC
LIMIT 5;
SQL

# ══════════════════════════════════════════════════════════════════════════════
#  4. RÉSEAU
# ══════════════════════════════════════════════════════════════════════════════
section "4. RÉSEAU"

# Ports en écoute
raw ""
raw "  Ports en écoute (TCP) :"
ss -tlnp 2>/dev/null | grep LISTEN | while read line; do
    echo "    $line" >> "$REPORT"
done

# Ports exposés publiquement (non 127.0.0.1)
PUBLIC_PORTS=$(ss -tlnp 2>/dev/null | grep LISTEN | grep -v "127.0.0.1\|::1" | awk '{print $4}')
if echo "$PUBLIC_PORTS" | grep -qE ":(3306|5432|6379|27017|9200)"; then
    critical "Base de données exposée publiquement ! Ports: $PUBLIC_PORTS"
else
    ok "Aucune base de données exposée publiquement"
fi

# Nombre de connexions actives
CONN_COUNT=$(ss -tn 2>/dev/null | grep ESTABLISHED | wc -l)
info "Connexions TCP établies : $CONN_COUNT"
if [ "$CONN_COUNT" -gt 200 ]; then
    warn "Nombre élevé de connexions : $CONN_COUNT"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  5. DOCKER
# ══════════════════════════════════════════════════════════════════════════════
section "5. DOCKER"

raw ""
raw "  État des containers :"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | \
    while read line; do echo "    $line" >> "$REPORT"; done

# Containers arrêtés
STOPPED=$(docker ps -a --filter "status=exited" --format "{{.Names}}" 2>/dev/null)
if [ -n "$STOPPED" ]; then
    warn "Containers arrêtés : $STOPPED"
else
    ok "Tous les containers sont en cours d'exécution"
fi

# Logs d'erreurs Odoo (dernières 24h)
raw ""
raw "  Erreurs Odoo (dernières 50 lignes) :"
docker logs --since 24h assurcore_web 2>&1 | \
    grep -E "ERROR|CRITICAL" | tail -10 | \
    while read line; do echo "    $line" >> "$REPORT"; done || true

ODOO_ERRORS=$(docker logs --since 24h assurcore_web 2>&1 | grep -c "ERROR\|CRITICAL" || echo "0")
if [ "$ODOO_ERRORS" -gt 50 ]; then
    warn "Nombreuses erreurs Odoo : $ODOO_ERRORS dans les dernières 24h"
elif [ "$ODOO_ERRORS" -gt 0 ]; then
    info "Erreurs Odoo dernières 24h : $ODOO_ERRORS"
else
    ok "Aucune erreur critique Odoo"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  6. SANTÉ APPLICATIVE ODOO / POSTGRESQL
# ══════════════════════════════════════════════════════════════════════════════
section "6. SANTÉ ODOO / POSTGRESQL"

# Health check Odoo
HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    "http://localhost:$ODOO_PORT/web/health" 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    ok "Odoo répond (HTTP $HTTP_STATUS) sur port $ODOO_PORT"
else
    critical "Odoo ne répond pas ! HTTP $HTTP_STATUS sur port $ODOO_PORT"
fi

# Statistiques base
raw ""
raw "  Statistiques base de données :"
docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db 2>/dev/null << 'SQL' | while read line; do echo "    $line" >> "$REPORT"; done
SELECT
    'Clients'      AS entite, COUNT(*) AS total FROM res_partner WHERE active=true
UNION ALL SELECT 'Polices',          COUNT(*) FROM insurance_policy
UNION ALL SELECT 'Operations',       COUNT(*) FROM insurance_operation
UNION ALL SELECT 'Quittances',       COUNT(*) FROM insurance_receipt
UNION ALL SELECT 'Reglements',       COUNT(*) FROM insurance_settlement
UNION ALL SELECT 'Sinistres',        COUNT(*) FROM insurance_claim
ORDER BY entite;
SQL

# Connexions PostgreSQL actives
PG_CONN=$(docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db -t \
    -c "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='assurcore_db';" \
    2>/dev/null | tr -d ' ' || echo "N/A")
info "Connexions PostgreSQL actives : $PG_CONN"
if echo "$PG_CONN" | grep -qE '^[0-9]+$' && [ "$PG_CONN" -gt 50 ]; then
    warn "Trop de connexions PostgreSQL : $PG_CONN"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  7. RESSOURCES SYSTÈME
# ══════════════════════════════════════════════════════════════════════════════
section "7. RESSOURCES SYSTÈME"

# CPU
LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | tr -d ',')
CPU_COUNT=$(nproc)
LOAD_INT=$(echo "$LOAD" | cut -d'.' -f1)
info "Charge CPU : $LOAD ($(nproc) cœurs)"
if [ "$LOAD_INT" -gt "$((CPU_COUNT * 2))" ]; then
    critical "Charge CPU très élevée : $LOAD (seuil=$((CPU_COUNT * 2)))"
elif [ "$LOAD_INT" -gt "$CPU_COUNT" ]; then
    warn "Charge CPU élevée : $LOAD"
else
    ok "Charge CPU normale : $LOAD"
fi

# RAM
TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')
USED_RAM=$(free -m | awk '/^Mem:/{print $3}')
RAM_PCT=$((USED_RAM * 100 / TOTAL_RAM))
info "RAM : ${USED_RAM}Mo / ${TOTAL_RAM}Mo (${RAM_PCT}%)"
if [ "$RAM_PCT" -gt 95 ]; then
    critical "RAM critique : ${RAM_PCT}% utilisée"
elif [ "$RAM_PCT" -gt "$MAX_RAM_PCT" ]; then
    warn "RAM élevée : ${RAM_PCT}% (seuil=$MAX_RAM_PCT%)"
else
    ok "RAM normale : ${RAM_PCT}%"
fi

# Top 5 processus par CPU
raw ""
raw "  Top 5 processus par CPU :"
ps aux --sort=-%cpu | head -6 | tail -5 | \
    while read line; do echo "    $line" >> "$REPORT"; done

# Top 5 processus par RAM
raw ""
raw "  Top 5 processus par RAM :"
ps aux --sort=-%mem | head -6 | tail -5 | \
    while read line; do echo "    $line" >> "$REPORT"; done

# ══════════════════════════════════════════════════════════════════════════════
#  8. GESTION DU STOCKAGE — ALERTES ET PROPOSITIONS DE NETTOYAGE
# ══════════════════════════════════════════════════════════════════════════════
section "8. GESTION DU STOCKAGE — ALERTES ET PROPOSITIONS"

raw ""
raw "  ⚠️  CE SCRIPT N'EFFECTUE AUCUN NETTOYAGE AUTOMATIQUE."
raw "  ⚠️  Les commandes ci-dessous sont des PROPOSITIONS — décision humaine requise."
raw ""

CLEANUP_NEEDED=0

# ── Helper pour proposer un nettoyage ─────────────────────────────────────────
propose() {
    local label="$1"
    local size="$2"
    local cmd="$3"
    local risk="$4"   # LOW / MEDIUM / HIGH
    CLEANUP_NEEDED=$((CLEANUP_NEEDED+1))
    raw ""
    raw "  ┌─ PROPOSITION #$CLEANUP_NEEDED ─────────────────────────────────────────"
    raw "  │  Cible    : $label"
    raw "  │  Taille   : $size"
    raw "  │  Risque   : $risk"
    raw "  │  Commande : $cmd"
    raw "  └───────────────────────────────────────────────────────────────"
}

# ── 8.1 Logs système /var/log ──────────────────────────────────────────────────
raw "  [8.1] Logs système /var/log"
VARLOG_SIZE=$(du -sh /var/log 2>/dev/null | awk '{print $1}')
VARLOG_MB=$(du -sm /var/log 2>/dev/null | awk '{print $1}')
info "Taille totale /var/log : $VARLOG_SIZE"

if [ "${VARLOG_MB:-0}" -gt 500 ]; then
    warn "/var/log dépasse 500 Mo : $VARLOG_SIZE"
    propose \
        "Logs système compressés anciens (>30 jours)" \
        "$(find /var/log -name '*.gz' -mtime +30 2>/dev/null | xargs du -sh 2>/dev/null | tail -1 | awk '{print $1}' || echo 'inconnu')" \
        "find /var/log -name '*.gz' -mtime +30 -delete" \
        "LOW — fichiers déjà compressés et archivés"
fi

# Log secure (tentatives SSH) peut grossir vite
SECURE_SIZE=$(du -sh /var/log/secure 2>/dev/null | awk '{print $1}' || echo "N/A")
SECURE_MB=$(du -sm /var/log/secure 2>/dev/null | awk '{print $1}' || echo "0")
info "Taille /var/log/secure (SSH) : $SECURE_SIZE"
if [ "${SECURE_MB:-0}" -gt 100 ]; then
    warn "/var/log/secure dépasse 100 Mo — nombreuses tentatives SSH archivées"
    propose \
        "/var/log/secure (logs SSH brute-force)" \
        "$SECURE_SIZE" \
        "journalctl --vacuum-time=7d  # OU: echo '' > /var/log/secure  (après backup)" \
        "MEDIUM — conserver une copie avant suppression"
fi

# ── 8.2 Logs Docker ────────────────────────────────────────────────────────────
raw ""
raw "  [8.2] Logs Docker containers"

for container in assurcore_web assurcore_db; do
    LOG_PATH=$(docker inspect --format='{{.LogPath}}' "$container" 2>/dev/null || echo "")
    if [ -n "$LOG_PATH" ] && [ -f "$LOG_PATH" ]; then
        LOG_SIZE=$(du -sh "$LOG_PATH" 2>/dev/null | awk '{print $1}')
        LOG_MB=$(du -sm "$LOG_PATH" 2>/dev/null | awk '{print $1}')
        info "Log $container : $LOG_SIZE"
        if [ "${LOG_MB:-0}" -gt 200 ]; then
            warn "Log Docker $container dépasse 200 Mo : $LOG_SIZE"
            propose \
                "Logs Docker container $container" \
                "$LOG_SIZE" \
                "docker logs $container --tail 1000 > /tmp/${container}_last1000.log && truncate -s 0 $LOG_PATH" \
                "LOW — sauvegarde des 1000 dernières lignes avant troncature"
        fi
    fi
done

# Espace total utilisé par Docker
DOCKER_TOTAL=$(docker system df 2>/dev/null | grep "Total Space" | awk '{print $4}' || echo "N/A")
raw ""
raw "  Résumé espace Docker :"
docker system df 2>/dev/null | while read line; do echo "    $line" >> "$REPORT"; done

# Images Docker inutilisées
DANGLING_IMAGES=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l)
if [ "$DANGLING_IMAGES" -gt 0 ]; then
    DANGLING_SIZE=$(docker images -f "dangling=true" --format "{{.Size}}" 2>/dev/null | head -5 | tr '\n' ' ')
    warn "$DANGLING_IMAGES image(s) Docker orphelines détectées"
    propose \
        "Images Docker orphelines (dangling)" \
        "$DANGLING_IMAGES images (~$DANGLING_SIZE)" \
        "docker image prune -f" \
        "LOW — images non taguées, sans container actif"
fi

# Volumes Docker inutilisés
UNUSED_VOLUMES=$(docker volume ls -qf dangling=true 2>/dev/null | wc -l)
if [ "$UNUSED_VOLUMES" -gt 0 ]; then
    warn "$UNUSED_VOLUMES volume(s) Docker inutilisé(s)"
    propose \
        "Volumes Docker inutilisés" \
        "$UNUSED_VOLUMES volumes" \
        "docker volume ls -qf dangling=true  # Vérifier d'abord, puis: docker volume prune -f" \
        "HIGH — vérifier qu'aucun volume de données n'est listé avant suppression"
fi

# ── 8.3 Filestore Odoo ────────────────────────────────────────────────────────
raw ""
raw "  [8.3] Filestore Odoo (pièces jointes, PDFs, images)"

FILESTORE_SIZE=$(docker exec assurcore_web du -sh /var/lib/odoo 2>/dev/null | awk '{print $1}' || echo "N/A")
FILESTORE_MB=$(docker exec assurcore_web du -sm /var/lib/odoo 2>/dev/null | awk '{print $1}' || echo "0")
info "Filestore Odoo : $FILESTORE_SIZE"

if [ "${FILESTORE_MB:-0}" -gt 1000 ]; then
    warn "Filestore Odoo dépasse 1 Go : $FILESTORE_SIZE"
    propose \
        "Pièces jointes Odoo orphelines (ir.attachment sans ressource)" \
        "$FILESTORE_SIZE total (portion orpheline inconnue)" \
        "# Depuis Odoo shell: env['ir.attachment'].search([('res_id','=',0)]) — analyser avant suppression" \
        "HIGH — analyse préalable requise via interface Odoo"
fi

# ── 8.4 PostgreSQL — WAL et tables gonflées ───────────────────────────────────
raw ""
raw "  [8.4] PostgreSQL — bloat et WAL"

# Tables avec beaucoup de dead tuples (besoin VACUUM)
raw ""
raw "  Tables nécessitant un VACUUM (dead_tuples > 10000) :"
docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db 2>/dev/null << 'SQL' >> "$REPORT"
SELECT
    relname AS table,
    n_dead_tup AS dead_tuples,
    pg_size_pretty(pg_total_relation_size(relid)) AS taille,
    last_vacuum::date AS dernier_vacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY n_dead_tup DESC
LIMIT 5;
SQL

DEAD_TUPLES=$(docker exec "$DB_NAME" psql -U "$DB_USER" assurcore_db -t \
    -c "SELECT COUNT(*) FROM pg_stat_user_tables WHERE n_dead_tup > 10000;" \
    2>/dev/null | tr -d ' ' || echo "0")

if [ "${DEAD_TUPLES:-0}" -gt 0 ]; then
    warn "$DEAD_TUPLES table(s) avec dead tuples excessifs → VACUUM recommandé"
    propose \
        "Tables PostgreSQL avec dead tuples ($DEAD_TUPLES tables)" \
        "Espace récupérable estimé : variable" \
        "docker exec assurcore_db psql -U odoo assurcore_db -c 'VACUUM ANALYZE;'" \
        "LOW — opération standard PostgreSQL, pas de perte de données"
fi

# Taille WAL
WAL_SIZE=$(docker exec "$DB_NAME" du -sh /var/lib/postgresql/data/pg_wal 2>/dev/null | awk '{print $1}' || echo "N/A")
info "Taille WAL PostgreSQL : $WAL_SIZE"

# ── 8.5 /tmp et fichiers temporaires ──────────────────────────────────────────
raw ""
raw "  [8.5] Fichiers temporaires"

TMP_SIZE=$(du -sh /tmp 2>/dev/null | awk '{print $1}')
TMP_MB=$(du -sm /tmp 2>/dev/null | awk '{print $1}')
info "Taille /tmp : $TMP_SIZE"

if [ "${TMP_MB:-0}" -gt 500 ]; then
    warn "/tmp dépasse 500 Mo : $TMP_SIZE"
    TMP_OLD=$(find /tmp -mtime +7 -not -path "/tmp/monitoring/*" 2>/dev/null | wc -l)
    propose \
        "Fichiers /tmp anciens (>7 jours, hors monitoring)" \
        "$TMP_OLD fichiers" \
        "find /tmp -mtime +7 -not -path '/tmp/monitoring/*' -delete" \
        "LOW — fichiers temporaires > 7 jours"
fi

# Rapports monitoring anciens (>60 jours)
OLD_REPORTS=$(find /tmp/monitoring -name "*.txt" -mtime +60 2>/dev/null | wc -l)
if [ "$OLD_REPORTS" -gt 0 ]; then
    OLD_SIZE=$(find /tmp/monitoring -name "*.txt" -mtime +60 2>/dev/null | xargs du -sh 2>/dev/null | tail -1 | awk '{print $1}' || echo "N/A")
    info "$OLD_REPORTS rapports monitoring anciens (>60 jours) : $OLD_SIZE"
    propose \
        "Rapports monitoring anciens > 60 jours" \
        "$OLD_SIZE ($OLD_REPORTS fichiers)" \
        "find /tmp/monitoring -name '*.txt' -mtime +60 -delete" \
        "LOW — rapports d'audit déjà consultés"
fi

# ── 8.6 Résumé propositions nettoyage ─────────────────────────────────────────
raw ""
if [ "$CLEANUP_NEEDED" -gt 0 ]; then
    raw "  ──────────────────────────────────────────────────────────────"
    raw "  TOTAL : $CLEANUP_NEEDED proposition(s) de nettoyage identifiée(s)"
    raw "  → Relire chaque proposition et décider cas par cas"
    raw "  → Faire un snapshot/backup AVANT tout nettoyage en production"
    raw "  ──────────────────────────────────────────────────────────────"
    warn "$CLEANUP_NEEDED action(s) de maintenance stockage recommandée(s)"
else
    ok "Stockage en bon état — aucun nettoyage nécessaire"
fi

# ══════════════════════════════════════════════════════════════════════════════
#  9. RÉSUMÉ ET SCORE DE RISQUE
# ══════════════════════════════════════════════════════════════════════════════
section "9. RÉSUMÉ ET SCORE DE RISQUE"

if [ "$CRITICALS" -gt 0 ]; then
    RISK_LEVEL="🔴 CRITIQUE"
    RISK_MSG="Action immédiate requise !"
elif [ "$WARNINGS" -gt 3 ]; then
    RISK_LEVEL="🟠 ÉLEVÉ"
    RISK_MSG="Plusieurs points nécessitent attention."
elif [ "$WARNINGS" -gt 0 ]; then
    RISK_LEVEL="🟡 MODÉRÉ"
    RISK_MSG="Quelques points à surveiller."
else
    RISK_LEVEL="🟢 BON"
    RISK_MSG="Système en bonne santé."
fi

cat >> "$REPORT" << SUMMARY

  Niveau de risque : $RISK_LEVEL
  Message          : $RISK_MSG

  Points critiques : $CRITICALS
  Avertissements   : $WARNINGS

  Rapport complet  : $REPORT
  Prochain rapport : demain à 06:00

SUMMARY

# Supprimer les anciens rapports (garder 30 jours)
find "$REPORT_DIR" -name "*.txt" -mtime +30 -delete 2>/dev/null || true

echo "Rapport genere : $REPORT"
echo "Critiques: $CRITICALS | Warnings: $WARNINGS"

# Exit code pour monitoring externe (nagios, zabbix, etc.)
[ "$CRITICALS" -gt 0 ] && exit 2
[ "$WARNINGS" -gt 0 ]  && exit 1
exit 0
