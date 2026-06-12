-- EVO02 — Correctifs post-import (set-based) : timbre OFF historique,
-- statuts de reglement, et recalcul des champs stockes du dashboard
-- (amount_open, payment_lead_days) que l'import SQL ne declenche pas.
BEGIN;

UPDATE insurance_receipt SET apply_timbre_fiscal = (name NOT LIKE 'ORA-FACT-%')
WHERE apply_timbre_fiscal IS DISTINCT FROM (name NOT LIKE 'ORA-FACT-%');

-- Encaisse par memoire (imputations actives uniquement)
CREATE TEMP TABLE tmp_paid AS
SELECT i.receipt_id,
       SUM(i.montant_impute) AS total_paid,
       MAX(i.date_imputation) AS last_pay
FROM insurance_settlement_imputation i
JOIN insurance_settlement s ON s.id = i.settlement_id
WHERE s.state IN ('regle', 'encaisse')
GROUP BY i.receipt_id;

-- Reste du stocke (balance des impayes)
UPDATE insurance_receipt r
SET amount_open = GREATEST(COALESCE(r.montant_prime, 0)
                           - COALESCE(p.total_paid, 0), 0)
FROM tmp_paid p WHERE p.receipt_id = r.id;
UPDATE insurance_receipt r
SET amount_open = COALESCE(r.montant_prime, 0)
WHERE NOT EXISTS (SELECT 1 FROM tmp_paid p WHERE p.receipt_id = r.id)
  AND r.amount_open IS DISTINCT FROM COALESCE(r.montant_prime, 0);

-- Delai de paiement (memoires soldees uniquement)
UPDATE insurance_receipt r
SET payment_lead_days = GREATEST((p.last_pay - r.date_emission), 0)
FROM tmp_paid p
WHERE p.receipt_id = r.id AND r.date_emission IS NOT NULL
  AND COALESCE(r.montant_prime, 0) > 0
  AND p.total_paid + 0.005 >= r.montant_prime;
UPDATE insurance_receipt r
SET payment_lead_days = NULL
FROM tmp_paid p
WHERE p.receipt_id = r.id
  AND p.total_paid + 0.005 < COALESCE(r.montant_prime, 0)
  AND r.payment_lead_days IS NOT NULL;

-- Statut de reglement des operations
UPDATE insurance_operation o
SET settlement_state = CASE
    WHEN COALESCE(p.total_paid, 0) <= 0.005 THEN 'non_reglee'
    WHEN COALESCE(p.total_paid, 0) < r.montant_prime - 0.005 THEN 'partielle'
    ELSE 'soldee'
  END
FROM insurance_receipt r
LEFT JOIN tmp_paid p ON p.receipt_id = r.id
WHERE o.receipt_id = r.id;
UPDATE insurance_operation SET settlement_state = 'non_facturee'
WHERE receipt_id IS NULL;

SELECT settlement_state, count(*) FROM insurance_operation GROUP BY 1 ORDER BY 2 DESC;
SELECT count(*) AS memoires_avec_reste FROM insurance_receipt WHERE amount_open > 0;
SELECT round(avg(payment_lead_days)) AS delai_moyen_jours FROM insurance_receipt WHERE payment_lead_days IS NOT NULL;
COMMIT;
