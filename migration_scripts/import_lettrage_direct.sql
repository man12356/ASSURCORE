TRUNCATE tmp_lettrage;
COPY tmp_lettrage FROM '/tmp/PR_REG_FACTURE_DATA_TABLE.tsv' WITH (FORMAT csv, DELIMITER E'\t', HEADER true, QUOTE '"');

-- Perform SQL update for lettrage
UPDATE insurance_settlement s
SET receipt_id = r.id, imputer = true
FROM tmp_lettrage t
JOIN insurance_receipt r ON r.name = 'ORA-FACT-' || t.annee_fact || '-' || t.num_facture
WHERE s.name = 'ORA-REG-' || t.num_reg
  AND t.supp_log != 'O';

-- Update the amount paid and states of the receipts
WITH payments AS (
  SELECT receipt_id, SUM(montant_reg) AS total_paid
  FROM insurance_settlement
  WHERE receipt_id IS NOT NULL AND state != 'annule'
  GROUP BY receipt_id
)
UPDATE insurance_receipt r
SET 
  state = CASE 
    WHEN p.total_paid >= r.amount_total * 0.99 THEN 'encaissee'
    ELSE 'partielle'
  END,
  amount_paid = CASE
    WHEN p.total_paid >= r.amount_total * 0.99 THEN r.amount_total
    ELSE p.total_paid
  END,
  amount_residual = GREATEST(0.0, r.amount_total - p.total_paid)
FROM payments p
WHERE r.id = p.receipt_id;
