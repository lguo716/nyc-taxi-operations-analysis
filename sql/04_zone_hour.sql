SELECT zone_id,date_trunc('hour',pickup_at) AS pickup_hour,count(*) AS trips
FROM fact_trip WHERE demand_valid GROUP BY ALL ORDER BY zone_id,pickup_hour;
