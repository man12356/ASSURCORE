#!/bin/bash
# =============================================================================
# upgrade_prod.sh — Safe Odoo module upgrade on VPS
# =============================================================================

echo "=== [1/2] Running module upgrade (assurcore) in database with alternate port ==="
docker-compose exec -T web odoo -d assurcore_db -u assurcore --http-port=8099 --stop-after-init

echo "=== [2/2] Restarting Odoo web service to reload updated registry ==="
docker-compose restart web

echo "=== Odoo module upgrade completed successfully! ==="
