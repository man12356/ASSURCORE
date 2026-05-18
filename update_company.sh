#!/bin/bash
# =============================================================================
# update_company.sh — Direct SQL update of company properties & currency
# =============================================================================

echo "=== [1/3] Activating TND currency in PostgreSQL ==="
docker-compose exec -T db psql -U odoo -d assurcore_db -c "UPDATE res_currency SET active = true WHERE id = 131;"

echo "=== [2/3] Updating Company Name and Currency directly ==="
docker-compose exec -T db psql -U odoo -d assurcore_db -c "UPDATE res_company SET name = 'COURTIER KAMOUN', currency_id = 131 WHERE id = 1;"

echo "=== [3/3] Updating Partner Name for the Company ==="
docker-compose exec -T db psql -U odoo -d assurcore_db -c "UPDATE res_partner SET name = 'COURTIER KAMOUN' WHERE id = (SELECT partner_id FROM res_company WHERE id = 1);"

echo "=== Company update completed successfully! ==="
