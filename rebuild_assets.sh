#!/bin/bash
# =============================================================================
# rebuild_assets.sh — Clear Odoo asset cache in PostgreSQL on VPS
# =============================================================================

echo "=== [1/2] Clearing Odoo asset attachments from database ==="
docker-compose exec -T db psql -U odoo -d assurcore_db -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"

echo "=== [2/2] Restarting Odoo web service to trigger recompilation ==="
docker-compose restart web

echo "=== Odoo asset cache rebuilt successfully! ==="
