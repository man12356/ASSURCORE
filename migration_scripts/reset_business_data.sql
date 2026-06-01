-- ============================================================
--  AssurCore — Reset des données métier
--  Conserve : configuration entreprise, utilisateurs, profils
--  Supprime : toutes les données importées depuis DATA_REEL
-- ============================================================

BEGIN;

-- 1. Sinistres
TRUNCATE TABLE insurance_claim RESTART IDENTITY CASCADE;

-- 2. Opérations / Avenants
TRUNCATE TABLE insurance_operation RESTART IDENTITY CASCADE;

-- 3. Quittances / Factures
TRUNCATE TABLE insurance_receipt RESTART IDENTITY CASCADE;

-- 4. Polices
TRUNCATE TABLE insurance_policy RESTART IDENTITY CASCADE;

-- 5. Banques importées
TRUNCATE TABLE insurance_bank RESTART IDENTITY CASCADE;

-- 6. Écritures comptables liées aux clients ORA-
--    (account_move référence res_partner via FK → supprimer avant les partenaires)
DELETE FROM account_move_line
WHERE move_id IN (
    SELECT id FROM account_move
    WHERE partner_id IN (
        SELECT id FROM res_partner WHERE ref LIKE 'ORA-%'
    )
);

DELETE FROM account_move
WHERE partner_id IN (
    SELECT id FROM res_partner WHERE ref LIKE 'ORA-%'
);

-- 7. Clients importés depuis Oracle (ref = 'ORA-XXXXX')
--    On ne touche PAS aux utilisateurs ni à la config entreprise
DELETE FROM res_partner
WHERE ref LIKE 'ORA-%'
  AND id NOT IN (SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL);

-- 8. Nettoyer messages mail liés aux objets supprimés
DELETE FROM mail_message
WHERE model IN (
    'insurance.claim',
    'insurance.operation',
    'insurance.receipt',
    'insurance.policy'
);

DELETE FROM mail_followers
WHERE res_model IN (
    'insurance.claim',
    'insurance.operation',
    'insurance.receipt',
    'insurance.policy'
);

-- 9. Nettoyer les pièces jointes
DELETE FROM ir_attachment
WHERE res_model IN (
    'insurance.claim',
    'insurance.operation',
    'insurance.receipt',
    'insurance.policy'
);

-- 10. Vérification finale
SELECT 'insurance_policy'        AS table_name, COUNT(*) AS lignes FROM insurance_policy
UNION ALL
SELECT 'insurance_receipt',                      COUNT(*) FROM insurance_receipt
UNION ALL
SELECT 'insurance_claim',                        COUNT(*) FROM insurance_claim
UNION ALL
SELECT 'insurance_operation',                    COUNT(*) FROM insurance_operation
UNION ALL
SELECT 'insurance_bank',                         COUNT(*) FROM insurance_bank
UNION ALL
SELECT 'res_partner (clients ORA)',              COUNT(*) FROM res_partner WHERE ref LIKE 'ORA-%'
UNION ALL
SELECT 'account_move (partenaires ORA restants)',COUNT(*) FROM account_move
    WHERE partner_id IN (SELECT id FROM res_partner WHERE ref LIKE 'ORA-%');

COMMIT;
