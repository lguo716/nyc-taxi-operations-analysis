-- Views are created by src.prepare.connect / src.verify; counts must reconcile exactly.
SELECT count(*) AS raw_rows,
 count(*) FILTER(WHERE NOT time_in_scope) AS outside_month,
 count(*) FILTER(WHERE time_in_scope AND is_voided) AS voided,
 count(*) FILTER(WHERE eligible_pickup AND NOT known_pickup) AS unknown_pickup,
 count(*) FILTER(WHERE demand_valid) AS demand_rows,
 count(*) FILTER(WHERE demand_valid AND fare_valid) AS fare_n,
 count(*) FILTER(WHERE demand_valid AND efficiency_valid) AS efficiency_n,
 count(*) FILTER(WHERE demand_valid AND tip_valid) AS tip_n
FROM fact_trip;
