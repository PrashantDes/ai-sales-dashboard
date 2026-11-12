WITH scoped AS (SELECT * FROM lines WHERE timestamp>=:start AND timestamp<:end AND (:country IS NULL OR country=:country)), grouped AS (
 SELECT stock_code AS group_key,
 SUM(CASE WHEN disposition='sale' THEN line_units ELSE 0 END) gross_units,
 -SUM(CASE WHEN disposition='cancellation' THEN line_units ELSE 0 END) cancellation_units
 FROM scoped WHERE disposition IN ('sale','cancellation') GROUP BY stock_code)
 SELECT *,CASE WHEN gross_units>0 THEN 1.0*cancellation_units/gross_units END cancellation_sales_ratio
 FROM grouped ORDER BY cancellation_units DESC,group_key;
