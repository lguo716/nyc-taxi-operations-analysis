SELECT source_month,count(*) AS trips,
 count(*) FILTER(WHERE fare_valid) AS fare_n,
 sum(fare_amount) FILTER(WHERE fare_valid) AS fare_sum,
 sum(total_amount) FILTER(WHERE fare_valid) AS total_charge_sum,
 sum(tip_amount) FILTER(WHERE tip_valid)/nullif(sum(fare_amount) FILTER(WHERE tip_valid),0) AS card_tip_rate
FROM fact_trip WHERE demand_valid GROUP BY source_month ORDER BY source_month;
