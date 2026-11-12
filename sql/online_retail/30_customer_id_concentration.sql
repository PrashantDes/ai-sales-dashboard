WITH scoped AS (SELECT * FROM lines WHERE timestamp>=:start AND timestamp<:end AND (:country IS NULL OR country=:country)), grouped AS (
 SELECT customer_id group_key,SUM(line_units) gross_units FROM scoped
 WHERE disposition='sale' AND customer_id IS NOT NULL GROUP BY customer_id), ranked AS (
 SELECT *,ROW_NUMBER() OVER(ORDER BY gross_units DESC,group_key) position,
 SUM(gross_units) OVER() population_units,
 SUM(gross_units) OVER(ORDER BY gross_units DESC,group_key ROWS UNBOUNDED PRECEDING) cumulative_units
 FROM grouped)
 SELECT * FROM ranked ORDER BY position;
