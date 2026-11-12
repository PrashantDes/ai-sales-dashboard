WITH scoped AS (SELECT * FROM lines WHERE timestamp>=:start AND timestamp<:end AND (:country IS NULL OR country=:country)), customers AS (
 SELECT customer_id,COUNT(DISTINCT invoice_id) invoice_count FROM scoped
 WHERE disposition='sale' AND customer_id IS NOT NULL GROUP BY customer_id
)
SELECT (SELECT COUNT(*) FROM customers) identified_customers,
 (SELECT COUNT(*) FROM customers WHERE invoice_count>=2) repeat_customers,
 CASE WHEN (SELECT COUNT(*) FROM customers)>0 THEN
 1.0*(SELECT COUNT(*) FROM customers WHERE invoice_count>=2)/(SELECT COUNT(*) FROM customers) END repeat_share,
 COALESCE(SUM(CASE WHEN disposition='sale' THEN line_units ELSE 0 END),0) gross_units,
 COALESCE(SUM(CASE WHEN disposition='sale' AND customer_id IS NOT NULL THEN line_units ELSE 0 END),0) identified_gross_units,
 COUNT(DISTINCT CASE WHEN disposition='sale' THEN invoice_id END) sales_invoices
FROM scoped;
