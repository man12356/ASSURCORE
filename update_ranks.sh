#!/bin/bash
# =============================================================================
# update_ranks.sh — Calculate and update customer_rank & client_state in DB
# =============================================================================

echo "=== [1/2] Updating customer_rank and client_state for all active insured partners ==="
docker-compose exec -T db psql -U odoo -d assurcore_db -c "
UPDATE res_partner
SET customer_rank = 1, client_state = 'actif'
WHERE id IN (
    SELECT DISTINCT partner_id FROM insurance_policy
    UNION
    SELECT DISTINCT partner_id FROM insurance_receipt
    UNION
    SELECT DISTINCT payer_id FROM insurance_receipt WHERE payer_id IS NOT NULL
);
"

echo "=== [2/2] Restarting Odoo web service to clear memory cache ==="
docker-compose restart web

echo "=== Ranks and client states updated successfully! ==="
