#!/bin/bash
# =============================================================================
# update_company.sh — Direct SQL update of company properties & currency
# =============================================================================

echo "=== [1/3] Activating TND currency in PostgreSQL ==="
docker compose -p assurcore exec -T db psql -U odoo -d assurcore_db -c "UPDATE res_currency SET active = true WHERE id = 131;"

echo "=== [2/3] Updating Company Name and Currency directly ==="
docker compose -p assurcore exec -T db psql -U odoo -d assurcore_db -c "UPDATE res_company SET name = 'ASSURANCES KAMOUN', currency_id = 131 WHERE id = 1;"

echo "=== [3/3] Updating Company Partner properties ==="
docker compose -p assurcore exec -T db psql -U odoo -d assurcore_db -c "
UPDATE res_partner SET 
    name = 'ASSURANCES KAMOUN',
    street = 'C01 Immeuble Carthage Palace',
    street2 = 'Centre Urbain Nord',
    city = 'Tunis',
    zip = '1082',
    phone = '+216 71 822 747',
    mobile = '+216 58 385 385',
    email = 'contact@assuranceskamoun.com',
    website = 'https://assuranceskamoun.com',
    country_id = 223
WHERE id = (SELECT partner_id FROM res_company WHERE id = 1);
"

echo "=== Company update completed successfully! ==="
