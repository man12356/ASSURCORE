#!/bin/bash
# =============================================================================
# rebuild_vps.sh — AssurCore EVO02 : rebuild + RE-IMPORT COMPLET (demo)
# Sequence identique a la validation locale du 12/06/2026 :
#   restore dump (config/users/compagnies) -> upgrade module ->
#   ETL SQL direct (clients/polices/memoires/operations/reglements/lettrage)
#   -> recalculs -> lot 4 (FIFO + anomalies) -> correctifs etats ->
#   tests evo02 -> purge assets -> restart
# =============================================================================
set -e
DC="docker-compose"
command -v docker-compose >/dev/null 2>&1 || DC="docker compose"

echo "=== [1/10] Preparation addons (module + TSV + scripts EVO02) ==="
mkdir -p addons data_db
rm -rf addons/assurcore addons/DATA_REEL
cp -rf assurcore addons/
cp -rf DATA_REEL_22-05-2026/DATA_REEL addons/DATA_REEL
cp -f migration_scripts/evo02_full_etl.py   addons/
cp -f migration_scripts/evo02_recompute.py  addons/
cp -f migration_scripts/evo02_lot4_migration.py addons/
cp -f migration_scripts/evo02_fix_states.sql   data_db/
cp -f migration_scripts/evo02_fix_clients.sql  data_db/

echo "=== [2/10] Restart containers ==="
$DC down || true
$DC up -d --build
$DC exec -u 0 -T web pip install openpyxl || true
echo "--- attente PostgreSQL ---"
for i in $(seq 1 30); do
  $DC exec -T db pg_isready -U odoo -d postgres_system >/dev/null 2>&1 && break
  sleep 5
done

echo "=== [3/10] Recreation base + restore dump (config/users) ==="
$DC stop web || true
$DC exec -T db dropdb -U odoo --if-exists assurcore_db || true
$DC exec -T db createdb -U odoo assurcore_db
$DC exec -T db pg_restore -U odoo -d assurcore_db --no-owner /backups/assurcore_db.dump || true

echo "=== [4/10] Upgrade module assurcore (schema EVO02) ==="
$DC run --rm -T web odoo -c /etc/odoo/odoo.conf -d assurcore_db -u assurcore --stop-after-init --workers 0

echo "=== [5/10] Generation SQL ETL (dans le conteneur web) ==="
$DC run --rm -T web python3 /mnt/extra-addons/evo02_full_etl.py
cp -f addons/evo02_full_import.sql data_db/

echo "=== [6/10] RESET + IMPORT metier (une transaction) ==="
$DC exec -T db psql -U odoo -d assurcore_db -v ON_ERROR_STOP=1 -q -f /backups/evo02_full_import.sql

echo "=== [7/10] Recalcul statuts + Lot 4 (FIFO + anomalies) ==="
$DC run --rm -T web sh -c "odoo shell -c /etc/odoo/odoo.conf -d assurcore_db --no-http < /mnt/extra-addons/evo02_recompute.py"
$DC run --rm -T web sh -c "odoo shell -c /etc/odoo/odoo.conf -d assurcore_db --no-http < /mnt/extra-addons/evo02_lot4_migration.py" | tee /tmp/lot4_vps.log
grep -q "RECETTE CONFORME" /tmp/lot4_vps.log && echo ">>> RECETTE CONFORME" || { echo ">>> ECHEC RECETTE LOT4"; exit 1; }

echo "=== [8/10] Correctifs etats (timbre OFF historique, statuts, clients actifs) ==="
$DC exec -T db psql -U odoo -d assurcore_db -q -f /backups/evo02_fix_states.sql
$DC exec -T db psql -U odoo -d assurcore_db -q -f /backups/evo02_fix_clients.sql

echo "=== [9/10] Tests EVO02 + purge assets ==="
$DC run --rm -T web odoo -c /etc/odoo/odoo.conf -d assurcore_db -u assurcore --test-tags evo02 --stop-after-init --workers 0 2>&1 | tee /tmp/tests_vps.log | grep -E "tests.result" || true
grep -q "0 failed, 0 error" /tmp/tests_vps.log && echo ">>> TESTS OK" || { echo ">>> ECHEC TESTS EVO02"; exit 1; }
$DC exec -T db psql -U odoo -d assurcore_db -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%' OR res_model='ir.ui.view';" || true

echo "=== [10/10] Restart final ==="
$DC restart web
echo "=== REBUILD EVO02 TERMINE — recette conforme, tests OK ==="
