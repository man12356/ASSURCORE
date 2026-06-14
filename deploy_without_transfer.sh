#!/bin/bash
# =============================================================================
# deploy_without_transfer.sh — AssurCore EVO03
# A lancer dans PuTTY apres transfert manuel des fichiers via WinSCP.
# Ne fait AUCUN transfert — uniquement les operations serveur.
#
# Usage :
#   ./deploy_without_transfer.sh            # upgrade + restart
#   ./deploy_without_transfer.sh --tests    # + execution tests evo02+evo03
#   ./deploy_without_transfer.sh --full     # + purge assets
# =============================================================================
set -e

RUN_TESTS=false
PURGE_ASSETS=false

for arg in "$@"; do
  case $arg in
    --tests) RUN_TESTS=true ;;
    --full)  RUN_TESTS=true; PURGE_ASSETS=true ;;
  esac
done

DC="docker-compose"
command -v docker-compose >/dev/null 2>&1 || DC="docker compose"

PROJECT_DIR="/mnt/sdb/assurcore_prod"
cd "$PROJECT_DIR"

echo ""
echo "============================================================"
echo "  AssurCore — Deploy (sans transfert) — $(date '+%d/%m/%Y %H:%M')"
echo "============================================================"
echo ""

# ── 1. Sync addons vers le conteneur ─────────────────────────────────────────
echo "=== [1/4] Copie addons/assurcore -> container mount ==="
rm -rf addons/assurcore
cp -rf assurcore addons/
echo "    OK"

# ── 2. Upgrade module Odoo ────────────────────────────────────────────────────
echo "=== [2/4] Upgrade module assurcore (-u assurcore) ==="
$DC run --rm -T web odoo \
    -c /etc/odoo/odoo.conf \
    -d assurcore_db \
    -u assurcore \
    --stop-after-init \
    --workers 0
echo "    OK"

# ── 3. Tests (optionnel) ──────────────────────────────────────────────────────
if [ "$RUN_TESTS" = true ]; then
  echo "=== [3/4] Tests (evo02 + evo03) ==="
  $DC run --rm -T web odoo \
      -c /etc/odoo/odoo.conf \
      -d assurcore_db \
      --test-tags evo02,evo03 \
      --stop-after-init \
      --workers 0 \
      2>&1 | tee /tmp/deploy_tests.log | grep -E "tests.result|ERROR|FAILED" || true

  if grep -q "0 failed, 0 error" /tmp/deploy_tests.log; then
    echo "    OK Tests passes"
  else
    echo ""
    echo "    ECHEC — voir : tail -n 50 /tmp/deploy_tests.log"
    echo ""
    # Ne pas bloquer le restart — afficher l'erreur et continuer
  fi
else
  echo "=== [3/4] Tests — SKIPPED (lancer avec --tests pour les activer) ==="
fi

# ── 4. Purge assets + Restart ─────────────────────────────────────────────────
echo "=== [4/4] Restart container web ==="
if [ "$PURGE_ASSETS" = true ]; then
  echo "    Purge assets cache..."
  $DC exec -T db psql -U odoo -d assurcore_db -c \
    "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%' OR res_model='ir.ui.view';" \
    >/dev/null 2>&1 || true
fi
$DC restart web

# Attendre que le conteneur reponde
echo "    Attente demarrage Odoo..."
for i in $(seq 1 24); do
  sleep 5
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    https://assurcore.metadidomi.com/web/health 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "    OK Odoo repond (HTTP 200) apres $((i*5))s"
    break
  fi
  if [ "$i" = "24" ]; then
    echo "    ! Odoo ne repond pas apres 120s — verifier : $DC logs --tail=30 web"
  fi
done

echo ""
echo "============================================================"
echo "  DEPLOY OK — https://assurcore.metadidomi.com"
echo "============================================================"
echo ""
