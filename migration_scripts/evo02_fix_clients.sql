-- Clients migres : statut 'actif' (le SQL direct ne pose pas le defaut Odoo)
UPDATE res_partner SET client_state = 'actif'
WHERE ref LIKE 'ORA-%' AND client_state IS NULL;
SELECT client_state, count(*) FROM res_partner WHERE ref LIKE 'ORA-%' GROUP BY 1;
