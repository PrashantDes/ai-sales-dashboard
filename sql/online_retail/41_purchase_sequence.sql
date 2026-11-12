-- Sequence observed purchases through end date, then restrict output to window.
WITH purchases AS (
 SELECT l.customer_id,l.invoice_id,MIN(l.timestamp) purchase_time
 FROM lines l JOIN invoices i ON l.invoice_id=i.invoice_id
 WHERE l.disposition='sale' AND l.customer_id IS NOT NULL AND l.timestamp<:end
 AND (:country IS NULL OR country=:country) GROUP BY l.customer_id,l.invoice_id
), sequenced AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY customer_id ORDER BY purchase_time,invoice_id) purchase_number
 FROM purchases)
SELECT * FROM sequenced WHERE purchase_time>=:start ORDER BY customer_id,purchase_time,invoice_id;
