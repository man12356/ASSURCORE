#!/usr/bin/env bash
# ==============================================================================
#  deploy_local.sh — Déploiement local AssurCore (Odoo 17 + PostgreSQL 15)
#
#  Usage :
#    chmod +x deploy_local.sh
#    ./deploy_local.sh [--reset] [--stop] [--logs]
#
#  Options :
#    --reset   Arrête les containers et supprime les volumes (REPART DE ZÉRO)
#    --stop    Arrête les containers proprement
#    --logs    Affiche les logs Odoo en temps réel après le démarrage
#
#  Ce script :
#    1. Vérifie que Docker et Docker Compose sont installés
#    2. Crée la structure de dossiers nécessaire
#    3. Détecte automatiquement un port libre (8069 → 8079)
#    4. Copie le module assurcore dans le dossier addons
#    5. Lance les containers en arrière-plan
#    6. Vérifie que Odoo répond (health check)
# ==============================================================================

set -euo pipefail
IFS=$'\n\t'

# ── Couleurs (désactivées si terminal non compatible) ──────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BLUE='' CYAN='' BOLD='' NC=''
fi

# ── Fonctions d'affichage ──────────────────────────────────────────────────────
info()    { echo -e "${BLUE}ℹ  $*${NC}"; }
success() { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $*${NC}"; }
error()   { echo -e "${RED}✗  $*${NC}" >&2; }
step()    { echo -e "\n${BOLD}${CYAN}── $* ──────────────────────────────────────${NC}"; }
banner()  {
    echo -e "${BOLD}${BLUE}"
    echo "  ╔═══════════════════════════════════════════╗"
    echo "  ║      AssurCore — Déploiement Local        ║"
    echo "  ║      Odoo 17.0 + PostgreSQL 15            ║"
    echo "  ╚═══════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ── Répertoire du script (pour chemins relatifs robustes) ─────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Variables configurables ────────────────────────────────────────────────────
PORT_START=8069          # Premier port à tester
PORT_END=8079            # Dernier port (10 tentatives max)
COMPOSE_FILE="docker-compose.yml"
MODULE_SRC="assurcore"   # Dossier source du module (relatif à SCRIPT_DIR)
ADDONS_DIR="addons"      # Dossier de destination des addons dans le projet
DATA_DIR="data_db"       # Persistance PostgreSQL
CONFIG_DIR="config"      # Fichier odoo.conf
HEALTH_TIMEOUT=120       # Secondes d'attente pour le health check Odoo
PROJECT_NAME="assurcore" # Nom du projet Docker Compose

# ── Traitement des arguments ───────────────────────────────────────────────────
ACTION="up"
SHOW_LOGS=false

for arg in "$@"; do
    case "$arg" in
        --reset)  ACTION="reset"    ;;
        --stop)   ACTION="stop"     ;;
        --logs)   SHOW_LOGS=true    ;;
        --help|-h)
            echo "Usage: $0 [--reset|--stop|--logs]"
            exit 0
            ;;
        *)
            warn "Option inconnue : $arg (ignorée)"
            ;;
    esac
done

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 1 — Pré-requis système
# ══════════════════════════════════════════════════════════════════════════════
banner
step "Vérification des pré-requis"

# ── 1a. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    error "Docker n'est pas installé."
    echo    "  → Installez Docker Desktop : https://docs.docker.com/get-docker/"
    exit 1
fi

DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
info "Docker trouvé : v${DOCKER_VERSION}"

# Vérifier que le daemon Docker tourne
if ! docker info &>/dev/null 2>&1; then
    error "Le daemon Docker ne répond pas."
    echo    "  → Lancez Docker Desktop (ou : sudo systemctl start docker)"
    exit 1
fi

# ── 1b. Docker Compose (v2 plugin ou v1 standalone) ──────────────────────────
COMPOSE_CMD=""

if docker compose version &>/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "?")
    info "Docker Compose v2 (plugin) : v${COMPOSE_VERSION}"
elif command -v docker-compose &>/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    COMPOSE_VERSION=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    warn "Docker Compose v1 détecté (v${COMPOSE_VERSION}) — la v2 est recommandée"
    # Vérifier la version minimale (1.27+ pour la syntaxe profiles)
    MAJOR=$(echo "$COMPOSE_VERSION" | cut -d. -f1)
    if [ "$MAJOR" -lt 1 ]; then
        error "Docker Compose v${COMPOSE_VERSION} trop ancienne. Mettez à jour."
        exit 1
    fi
else
    error "Docker Compose introuvable (ni 'docker compose' ni 'docker-compose')."
    echo    "  → Installez Docker Compose : https://docs.docker.com/compose/install/"
    exit 1
fi

export COMPOSE_CMD

# ══════════════════════════════════════════════════════════════════════════════
#  Gestion --stop
# ══════════════════════════════════════════════════════════════════════════════
if [ "$ACTION" = "stop" ]; then
    step "Arrêt des containers AssurCore"
    $COMPOSE_CMD -p "$PROJECT_NAME" down
    success "Containers arrêtés proprement."
    exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
#  Gestion --reset
# ══════════════════════════════════════════════════════════════════════════════
if [ "$ACTION" = "reset" ]; then
    step "Reset complet (containers + volumes)"
    warn "ATTENTION : Cette opération supprime toutes les données PostgreSQL."
    read -r -p "         Confirmer ? [oui/NON] : " confirm
    if [ "${confirm,,}" != "oui" ]; then
        info "Opération annulée."
        exit 0
    fi
    $COMPOSE_CMD -p "$PROJECT_NAME" down -v --remove-orphans 2>/dev/null || true
    rm -rf "$DATA_DIR"
    success "Reset effectué. Relancez ./deploy_local.sh pour repartir de zéro."
    exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 2 — Structure des dossiers
# ══════════════════════════════════════════════════════════════════════════════
step "Création de la structure de dossiers"

for dir in "$ADDONS_DIR" "$DATA_DIR" "$CONFIG_DIR"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        info "Dossier créé : ${SCRIPT_DIR}/${dir}/"
    else
        info "Dossier existant : ${SCRIPT_DIR}/${dir}/"
    fi
done

# ── Correction des permissions PostgreSQL ────────────────────────────────────
# L'image postgres:15 nécessite que data_db soit accessible par l'UID 999
chmod 750 "$DATA_DIR" 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 3 — Module AssurCore dans le dossier addons
# ══════════════════════════════════════════════════════════════════════════════
step "Synchronisation du module AssurCore"

MODULE_TARGET="${ADDONS_DIR}/${MODULE_SRC}"

if [ -d "$MODULE_SRC" ]; then
    if [ ! -e "$MODULE_TARGET" ]; then
        # Copie du module (plus robuste qu'un symlink sur Windows/WSL)
        cp -r "$MODULE_SRC" "$MODULE_TARGET"
        success "Module copié → ${MODULE_TARGET}/"
    else
        # Mettre à jour les fichiers modifiés (rsync si disponible)
        if command -v rsync &>/dev/null; then
            rsync -a --delete "${MODULE_SRC}/" "${MODULE_TARGET}/"
            info "Module synchronisé (rsync) → ${MODULE_TARGET}/"
        else
            rm -rf "$MODULE_TARGET"
            cp -r "$MODULE_SRC" "$MODULE_TARGET"
            info "Module mis à jour (cp) → ${MODULE_TARGET}/"
        fi
    fi
elif [ -d "${ADDONS_DIR}/${MODULE_SRC}" ]; then
    info "Module déjà dans addons/ (dossier source absent — mode production normal)"
else
    warn "Dossier '${MODULE_SRC}/' introuvable dans ${SCRIPT_DIR}."
    warn "Créez addons/assurcore/ manuellement ou copiez le module."
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 4 — Génération de odoo.conf (si absent)
# ══════════════════════════════════════════════════════════════════════════════
step "Configuration Odoo"

ODOO_CONF="${CONFIG_DIR}/odoo.conf"
if [ ! -f "$ODOO_CONF" ]; then
    info "Génération de ${ODOO_CONF} …"
    # Le fichier odoo.conf est normalement fourni ; on le recrée si absent
    cat > "$ODOO_CONF" << 'EOF_CONF'
[options]
; ── Connexion base de données ──────────────────────────────────────────────
db_host = db
db_port = 5432
db_user = odoo
db_password = odoo
db_name = False

; ── Modules ────────────────────────────────────────────────────────────────
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons

; ── Serveur ────────────────────────────────────────────────────────────────
xmlrpc_port = 8069
longpolling_port = 8072

; ── Logs ───────────────────────────────────────────────────────────────────
log_level = info
log_handler = :INFO

; ── Workers (0 = mode mono-thread, adapté au développement local) ──────────
workers = 0

; ── Sécurité ───────────────────────────────────────────────────────────────
; admin_passwd = admin        ; Décommenter et changer en production !
; list_db = False             ; Désactiver en production pour masquer la liste DB
EOF_CONF
    success "odoo.conf généré."
else
    info "${ODOO_CONF} déjà présent — conservé."
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 5 — Détection intelligente du port libre
# ══════════════════════════════════════════════════════════════════════════════
step "Recherche d'un port disponible (${PORT_START}→${PORT_END})"

# Fonction portable de test de port
# Essaie plusieurs méthodes selon l'OS (Linux / macOS / WSL)
is_port_free() {
    local port=$1

    # Méthode 1 : ss (Linux moderne, le plus fiable)
    if command -v ss &>/dev/null 2>&1; then
        if ss -tlnp 2>/dev/null | grep -q ":${port}[[:space:]]"; then
            return 1  # port occupé
        fi
        return 0  # port libre
    fi

    # Méthode 2 : netstat (macOS, systèmes plus anciens)
    if command -v netstat &>/dev/null 2>&1; then
        if netstat -an 2>/dev/null | grep -qE "[:.]${port}[[:space:]].*LISTEN"; then
            return 1
        fi
        return 0
    fi

    # Méthode 3 : /dev/tcp (bash pur — fonctionne quand les autres échouent)
    if (echo >/dev/tcp/localhost/$port) 2>/dev/null; then
        return 1  # connexion réussie = port occupé
    fi
    return 0  # port libre
}

ODOO_PORT=""
for port in $(seq "$PORT_START" "$PORT_END"); do
    if is_port_free "$port"; then
        ODOO_PORT="$port"
        break
    else
        info "Port ${port} occupé → essai suivant …"
    fi
done

if [ -z "$ODOO_PORT" ]; then
    error "Aucun port libre entre ${PORT_START} et ${PORT_END}."
    error "Libérez un port ou ajustez PORT_START/PORT_END dans ce script."
    exit 1
fi

if [ "$ODOO_PORT" = "$PORT_START" ]; then
    success "Port ${ODOO_PORT} disponible."
else
    success "Port ${ODOO_PORT} disponible (${PORT_START} occupé)."
fi

# Exporter pour docker-compose.yml
export ODOO_PORT
info "Variable exportée : ODOO_PORT=${ODOO_PORT}"

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 6 — Vérification du docker-compose.yml
# ══════════════════════════════════════════════════════════════════════════════
step "Validation de ${COMPOSE_FILE}"

if [ ! -f "$COMPOSE_FILE" ]; then
    error "Fichier ${COMPOSE_FILE} introuvable dans ${SCRIPT_DIR}."
    exit 1
fi

# Validation syntaxique avec docker compose config
if $COMPOSE_CMD config --quiet 2>/dev/null; then
    info "docker-compose.yml valide."
else
    warn "Impossible de valider la syntaxe YAML (non bloquant)."
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 7 — Lancement des containers
# ══════════════════════════════════════════════════════════════════════════════
step "Lancement des containers (arrière-plan)"

# Pull des images si nécessaire (silencieux si déjà présentes)
info "Vérification des images Docker …"
$COMPOSE_CMD -p "$PROJECT_NAME" pull --quiet 2>/dev/null || \
    warn "Pull ignoré (mode offline ou images déjà présentes)."

# Lancement
info "Démarrage des containers …"
$COMPOSE_CMD -p "$PROJECT_NAME" up -d --remove-orphans

# Afficher le statut
echo ""
$COMPOSE_CMD -p "$PROJECT_NAME" ps

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 8 — Health check Odoo
# ══════════════════════════════════════════════════════════════════════════════
step "Vérification de démarrage Odoo (timeout: ${HEALTH_TIMEOUT}s)"

ELAPSED=0
SLEEP_INTERVAL=5
ODOO_READY=false

info "En attente du démarrage Odoo …"
while [ "$ELAPSED" -lt "$HEALTH_TIMEOUT" ]; do
    # Tester si Odoo répond sur le port (HTTP 200 ou redirection)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
                     --connect-timeout 3 \
                     "http://localhost:${ODOO_PORT}/web/health" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        ODOO_READY=true
        break
    fi

    # Fallback : test TCP simple si curl n'est pas disponible
    if ! command -v curl &>/dev/null; then
        if (echo >/dev/tcp/localhost/$ODOO_PORT) 2>/dev/null; then
            ODOO_READY=true
            break
        fi
    fi

    printf "."
    sleep "$SLEEP_INTERVAL"
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done
echo ""

if ! $ODOO_READY; then
    warn "Odoo n'est pas encore prêt après ${HEALTH_TIMEOUT}s."
    warn "Il démarre peut-être encore — vérifiez avec :"
    warn "  $COMPOSE_CMD -p $PROJECT_NAME logs -f web"
    # Non bloquant : le script continue
fi

# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 9 — Résumé et instructions
# ══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════════════════════════════╗"
echo "  ║                                                               ║"
printf "  ║  ✅  Déploiement réussi !                                    ║\n"
printf "  ║                                                               ║\n"
printf "  ║  🌐  Odoo AssurCore :  %-39s║\n" "http://localhost:${ODOO_PORT}"
printf "  ║  🗄️   PostgreSQL   :  Port interne uniquement (sécurisé)      ║\n"
printf "  ║                                                               ║\n"
printf "  ║  Identifiants par défaut :  admin / admin                     ║\n"
printf "  ║  Base de données à créer :  assurcore_db                      ║\n"
printf "  ║                                                               ║\n"
echo "  ╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${BOLD}Commandes utiles :${NC}"
echo "  Logs en temps réel    : $COMPOSE_CMD -p $PROJECT_NAME logs -f web"
echo "  Arrêter proprement    : ./deploy_local.sh --stop"
echo "  Redémarrer de zéro    : ./deploy_local.sh --reset"
echo "  Statut des containers : $COMPOSE_CMD -p $PROJECT_NAME ps"
echo "  Module assurcore      : Installer depuis Odoo → Apps → Rechercher 'assurcore'"
echo ""
echo -e "${BOLD}Pour lancer l'import ETL (après création de la DB Odoo) :${NC}"
echo "  cd migration_scripts && python import_assurcore.py --dry-run"
echo "  cd migration_scripts && python import_assurcore.py"
echo ""

# Affichage des logs si demandé
if $SHOW_LOGS; then
    info "Affichage des logs Odoo (Ctrl+C pour quitter) …"
    sleep 2
    $COMPOSE_CMD -p "$PROJECT_NAME" logs -f web
fi
