-- EVO02 — Timbre fiscal optionnel : OFF sur l'historique migre, ON ailleurs
-- + recalcul SQL set-based des statuts de reglement.
BEGIN;
UPDATE insurance_receipt SET apply_timbre_fiscal = (name NOT LIKE 'ORA-FACT-%')
WHERE apply_timbre_fiscal IS DISTINCT FROM (name NOT LIKE 'ORA-FACT-%');

WITH paid AS (
  SELECT i.receipt_id, SUM(i.montant_impute) AS total_paid
  FROM insurance_settlement_imputation i
  JOIN insurance_settlement s ON s.id = i.settlement_id
  WHERE s.state IN ('regle', 'encaisse')
  GROUP BY i.receipt_id
)
UPDATE insurance_operation o
SET settlement_state = CASE
    WHEN COALESCE(p.total_paid, 0) <= 0.005 THEN 'non_reglee'
    WHEN COALESCE(p.total_paid, 0) < r.montant_prime - 0.005 THEN 'partielle'
    ELSE 'soldee'
  END
FROM insurance_receipt r
LEFT JOIN paid p ON p.receipt_id = r.id
WHERE o.receipt_id = r.id;

UPDATE insurance_operation SET settlement_state = 'non_facturee'
WHERE receipt_id IS NULL;

SELECT settlement_state, count(*) FROM insurance_operation GROUP BY settlement_state ORDER BY 2 DESC;
SELECT apply_timbre_fiscal, count(*) FROM insurance_receipt GROUP BY 1;
COMMIT;
