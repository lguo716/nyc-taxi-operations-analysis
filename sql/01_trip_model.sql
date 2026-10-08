-- Applied separately to each complete monthly Parquet; source_month and source_path are supplied by prepare.py.
WITH base AS (
 SELECT file_row_number::BIGINT AS source_row, '{month}'::VARCHAR AS source_month,
 VendorID, tpep_pickup_datetime AS pickup_at, tpep_dropoff_datetime AS dropoff_at,
 TRY_CAST(PULocationID AS INTEGER) AS zone_id, TRY_CAST(DOLocationID AS INTEGER) AS dropoff_zone_id,
 passenger_count, RatecodeID, payment_type, trip_distance, fare_amount, total_amount, tip_amount,
 extra, mta_tax, tolls_amount, improvement_surcharge, congestion_surcharge, airport_fee, cbd_congestion_fee,
 date_trunc('hour',tpep_pickup_datetime) AS pickup_hour,
 datediff('millisecond',tpep_pickup_datetime,tpep_dropoff_datetime)/60000.0 AS duration_min,
 trip_distance*1.609344 AS distance_km,
 COALESCE(strftime(tpep_pickup_datetime,'%Y-%m')='{month}',FALSE) AS time_in_scope,
 COALESCE(payment_type=6,FALSE) AS is_voided,
 COALESCE(PULocationID BETWEEN 1 AND 263,FALSE) AS known_pickup,
 COALESCE(DOLocationID BETWEEN 1 AND 263,FALSE) AS known_dropoff,
 CAST(tpep_pickup_datetime AS DATE) IN (DATE '2025-03-09',DATE '2025-11-02')
 OR CAST(tpep_dropoff_datetime AS DATE) IN (DATE '2025-03-09',DATE '2025-11-02') AS dst_efficiency_excluded
 FROM read_parquet('{source_path}',file_row_number=TRUE)
), flags AS (
 SELECT *,
 COALESCE(duration_min<=0 OR duration_min>180 OR NOT isfinite(duration_min),TRUE) AS bad_duration,
 COALESCE(trip_distance<=0 OR trip_distance>100 OR NOT isfinite(trip_distance),TRUE) AS bad_distance,
 CASE WHEN duration_min>0 THEN distance_km/(duration_min/60) END AS speed_kmh,
 COALESCE(fare_amount<0 OR total_amount<0 OR tip_amount<0 OR tolls_amount<0 OR extra<0
 OR mta_tax<0 OR improvement_surcharge<0 OR congestion_surcharge<0 OR airport_fee<0 OR cbd_congestion_fee<0,FALSE) AS negative_amount,
 COALESCE(fare_amount>1000 OR total_amount>2000 OR tip_amount>1000,FALSE) AS extreme_amount,
 COALESCE(fare_amount IS NULL OR total_amount IS NULL OR NOT isfinite(fare_amount) OR NOT isfinite(total_amount),TRUE) AS missing_amount
 FROM base
), eligibility AS (
 SELECT *,
 time_in_scope AND NOT is_voided AS eligible_pickup,
 time_in_scope AND NOT is_voided AND known_pickup AS demand_valid,
 COALESCE(speed_kmh>130 OR speed_kmh<0 OR NOT isfinite(speed_kmh),TRUE) AS bad_speed,
 COALESCE(payment_type IN (0,1,2) AND fare_amount>0 AND total_amount>0
 AND NOT negative_amount AND NOT extreme_amount AND NOT missing_amount,FALSE) AS fare_valid,
 NOT bad_duration AND NOT bad_distance AND NOT COALESCE(dst_efficiency_excluded,TRUE)
 AND COALESCE(speed_kmh BETWEEN 0 AND 130,FALSE) AS efficiency_valid
 FROM flags
)
SELECT *,
 fare_valid AND payment_type=1 AND tip_amount IS NOT NULL AND isfinite(tip_amount) AS tip_valid,
 (NOT time_in_scope OR is_voided OR NOT known_pickup OR NOT known_dropoff OR bad_duration OR bad_distance OR bad_speed OR negative_amount OR extreme_amount OR missing_amount) AS any_quality_flag
FROM eligibility
