-- Complete observed calendar months wholly inside the selected interval.
WITH scoped AS (SELECT * FROM lines WHERE timestamp>=:start AND timestamp<:end AND (:country IS NULL OR country=:country)), monthly AS (
 SELECT strftime('%Y-%m-01',timestamp) month,
 SUM(CASE WHEN disposition='sale' THEN line_units ELSE 0 END) gross_units,
 -SUM(CASE WHEN disposition='cancellation' THEN line_units ELSE 0 END) cancellation_units,
 COUNT(DISTINCT CASE WHEN disposition='sale' THEN invoice_id END) sales_invoices
 FROM scoped GROUP BY month
), complete AS (
 SELECT * FROM monthly WHERE month>=:start AND date(month,'+1 month')<=date(:end)
 AND month<(SELECT strftime('%Y-%m-01',max(timestamp)) FROM lines)
), previous AS (
 SELECT *,LAG(month) OVER(ORDER BY month) previous_month,
 LAG(gross_units) OVER(ORDER BY month) previous_gross FROM complete
)
SELECT month,gross_units,cancellation_units,gross_units-cancellation_units net_units,sales_invoices,
 CASE WHEN date(previous_month,'+1 month')=month AND previous_gross>0
 THEN 1.0*(gross_units-previous_gross)/previous_gross END growth
FROM previous ORDER BY month;
