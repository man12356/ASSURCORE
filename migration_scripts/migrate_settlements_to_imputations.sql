-- ==============================================================================
--  migrate_settlements_to_imputations.sql
--  Refactoring architectural : suppression du lien direct settlement→receipt
--  Conversion des 21 453 liens directs en enregistrements insurance.settlement.imputation
--
--  Contexte : fidélité à Oracle (PR_REGELEMENT n'a pas de lien direct avec
--             PR_OPERATION — tout passe par PR_COMPENSATION_REGLEMENT)
--
--  Exécution : docker exec -i assurcore_db psql -U odoo assurcore_db < ce_fichier.sql
-- ==============================================================================

BEGIN;

-- ==============================================================================
-- ÉTAPE 1 : Créer les imputations depuis les liens directs existants
--           (settlement.receipt_id → imputation record)
-- ==============================================================================

INSERT INTO insurance_settlement_imputation
    (settlement_id, receipt_id, montant_impute, date_imputation,
     create_date, write_date)
SELECT
    s.id,
    s.receipt_id,
    s.montant_reg,
    COALESCE(s.date_reg, CURRENT_DATE),
    NOW(),
    NOW()
FROM insurance_settlement s
WHERE s.receipt_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM insurance_settlement_imputation i
    WHERE i.settlement_id = s.id
      AND i.receipt_id    = s.receipt_id
  );

-- Résultat attendu : ~21 453 lignes insérées
-- (hors doublons déjà existants)

-- ==============================================================================
-- ÉTAPE 2 : Mettre à jour montant_restant sur les règlements
--           (= montant_reg - somme des imputations, min 0)
-- ==============================================================================

UPDATE insurance_settlement s
SET montant_restant = GREATEST(0,
    s.montant_reg - COALESCE(
        (SELECT SUM(i.montant_impute)
         FROM insurance_settlement_imputation i
         WHERE i.settlement_id = s.id),
        0
    )
);

-- ==============================================================================
-- ÉTAPE 3 : Recalculer amount_paid sur toutes les quittances
--           (uniquement depuis les imputations — plus depuis receipt_id direct)
-- ==============================================================================

UPDATE insurance_receipt r
SET
    amount_paid = COALESCE(sub.total_paye, 0),
    amount_residual = r.amount_total - COALESCE(sub.total_paye, 0)
FROM (
    SELECT
        i.receipt_id,
        SUM(i.montant_impute) AS total_paye
    FROM insurance_settlement_imputation i
    JOIN insurance_settlement s ON s.id = i.settlement_id
    WHERE s.state IN ('regle', 'encaisse')
    GROUP BY i.receipt_id
) sub
WHERE r.id = sub.receipt_id;

-- ==============================================================================
-- ÉTAPE 4 : Vider receipt_id sur les settlements (optionnel — laisser en legacy)
--           Décommenté uniquement si on veut une suppression propre
-- ==============================================================================
-- UPDATE insurance_settlement SET receipt_id = NULL WHERE receipt_id IS NOT NULL;

COMMIT;

-- ==============================================================================
-- VÉRIFICATIONS
-- ==============================================================================

SELECT
    'Imputations créées'        AS metrique,
    COUNT(*)::text              AS valeur
FROM insurance_settlement_imputation

UNION ALL SELECT
    'Règlements avec solde > 0',
    COUNT(*)::text
FROM insurance_settlement
WHERE montant_restant > 0

UNION ALL SELECT
    'Quittances avec amount_paid > 0',
    COUNT(*)::text
FROM insurance_receipt
WHERE amount_paid > 0

UNION ALL SELECT
    'Total encaissé (TND)',
    ROUND(SUM(amount_paid)::numeric, 0)::text
FROM insurance_receipt

UNION ALL SELECT
    'Total restant dû (TND)',
    ROUND(SUM(amount_residual)::numeric, 0)::text
FROM insurance_receipt
WHERE amount_residual > 0;
