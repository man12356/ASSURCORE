-- Clients migres : statut 'actif' (le SQL direct ne pose pas le defaut Odoo)
UPDATE res_partner SET client_state = 'actif'
WHERE ref LIKE 'ORA-%'
  AND (client_state IS NULL OR client_state = 'prospect');
SELECT client_state, count(*) FROM res_partner WHERE ref LIKE 'ORA-%' GROUP BY 1;
SELECT count(*) AS clients_actifs_visibles FROM res_partner
WHERE client_state = 'actif' AND customer_rank > 0 AND active = TRUE;
