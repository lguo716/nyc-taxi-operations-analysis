import logging
import zipfile
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .config import ROOT, MONTHS, HOLIDAYS, ensure_dirs
from .utils import read_json, write_json, sha256, csv

REQUIRED = {"VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "PULocationID", "DOLocationID", "trip_distance", "fare_amount", "total_amount", "tip_amount", "payment_type", "cbd_congestion_fee"}

def require_complete_sources(manifest):
    paths = {item["relative_path"]: item for item in manifest["files"]}
    if not manifest.get("complete"):
        raise ValueError("Source manifest is incomplete")
    for month in MONTHS:
        relative = f"data/raw/yellow_tripdata_{month}.parquet"
        if relative not in paths or not (ROOT / relative).exists():
            raise ValueError(f"Missing month {month}; zero filling is forbidden")
    return paths

def connect():
    connection = duckdb.connect(str(ROOT / "data/processed/nyc_taxi.duckdb"))
    connection.execute("SET threads=4")
    connection.execute("SET memory_limit='8GB'")
    connection.execute("SET preserve_insertion_order=false")
    connection.execute("SET temp_directory=?", [str(ROOT / "data/tmp")])
    return connection

def boundaries():
    import shapefile
    from pyproj import CRS, Transformer
    from shapely.geometry import shape, mapping
    from shapely.ops import transform, unary_union
    folder = ROOT / "data/reference/zones"
    folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(ROOT / "data/reference/taxi_zones.zip") as archive:
        for item in archive.infolist():
            target = (folder / item.filename).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise ValueError("Unsafe zip path")
        archive.extractall(folder)
    shp = next(folder.rglob("*.shp"))
    crs = CRS.from_wkt(shp.with_suffix(".prj").read_text())
    transformer = Transformer.from_crs(crs, 4326, always_xy=True)
    reader = shapefile.Reader(str(shp))
    features = []
    # Some zones have multiple polygons; dissolve by LocationID to guarantee unique map keys.
    groups = {}
    for record in reader.iterShapeRecords():
        props = record.record.as_dict()
        zone = int(props["LocationID"])
        geom = transform(transformer.transform, shape(record.shape.__geo_interface__))
        groups.setdefault(zone, []).append(geom)
    for zone, geometries in sorted(groups.items()):
        geom = unary_union(geometries).simplify(0.00008, preserve_topology=True)
        features.append({"type": "Feature", "id": str(zone), "properties": {"zone_key": str(zone), "LocationID": str(zone)}, "geometry": mapping(geom)})
    write_json(ROOT / "powerbi/taxi_zones.geojson", {"type": "FeatureCollection", "features": features})
    write_json(ROOT / "data/reference/boundary_manifest.json", {"source_crs": crs.to_string(), "output_crs": "EPSG:4326", "zone_count": len(features), "zone_ids": sorted(groups), "simplification_degrees": 0.00008})

def prepare():
    ensure_dirs()
    sources = require_complete_sources(read_json(ROOT / "data/source_manifest.json"))
    lookup = pd.read_csv(ROOT / "data/reference/taxi_zone_lookup.csv")
    lookup = lookup.rename(columns={"LocationID": "zone_id", "Borough": "borough", "Zone": "zone", "service_zone": "service_zone"})
    lookup["zone_key"] = lookup.zone_id.astype(str)
    lookup["zone_label"] = lookup.zone_id.astype(str) + " · " + lookup.zone.fillna("Unknown")
    csv(lookup, "dim_zone")
    weather = read_json(ROOT / "data/reference/weather_2025.json")
    daily = pd.DataFrame(weather["daily"]).rename(columns={"time": "date"})
    if daily.date.duplicated().any() or daily.date.nunique() != 365:
        raise ValueError("Weather dates must be unique and complete")
    daily["date"] = pd.to_datetime(daily.date)
    daily["weekday"] = daily.date.dt.dayofweek
    daily["month"] = daily.date.dt.month
    daily["is_weekend"] = (daily.weekday>=5).astype(int)
    daily["is_holiday"] = daily.date.dt.strftime("%Y-%m-%d").isin(HOLIDAYS).astype(int)
    daily["holiday_name"] = daily.date.dt.strftime("%Y-%m-%d").map(HOLIDAYS).fillna("")
    daily["weather_group"] = np.select([daily.snowfall_sum>0, daily.precipitation_sum>=1], ["降雪", "降水"], default="无明显降水")
    daily["day_type"] = np.select([daily.is_holiday==1, daily.is_weekend==1], ["节假日", "周末"], default="工作日")
    daily["month_label"] = daily.date.dt.strftime("%Y-%m")
    csv(daily, "dim_date")
    csv(pd.DataFrame({"hour": range(24), "hour_label": [f"{x:02d}:00" for x in range(24)]}), "dim_hour")
    boundaries()
    connection = connect()
    trip_folder = ROOT / "data/processed/trips"
    trip_folder.mkdir(exist_ok=True)
    cache_path = ROOT / "data/processed/prepare_manifest.json"
    old = read_json(cache_path) if cache_path.exists() else {"months": {}}
    code_hash = sha256(Path(__file__)) + sha256(ROOT / "sql/01_trip_model.sql")
    quality_rows, month_cache = [], {}
    sql_template = (ROOT / "sql/01_trip_model.sql").read_text(encoding="utf-8")
    for month in MONTHS:
        relative = f"data/raw/yellow_tripdata_{month}.parquet"
        raw, item = ROOT / relative, sources[relative]
        if sha256(raw) != item["sha256"]:
            raise ValueError(f"Source SHA256 mismatch: {month}")
        columns = set(pq.read_schema(raw).names)
        if not REQUIRED.issubset(columns):
            raise ValueError(f"Missing fields for {month}: {REQUIRED-columns}")
        output = trip_folder / f"{month}.parquet"
        cached = old["months"].get(month)
        if cached and output.exists() and cached["source_sha256"] == item["sha256"] and cached["code_hash"] == code_hash and cached["output_sha256"] == sha256(output):
            logging.info("Reuse processed month %s", month)
            quality = cached["quality"]
        else:
            logging.info("Preparing all %s records for %s", item["rows"], month)
            query = sql_template.format(month=month, source_path=raw.as_posix())
            connection.execute(f"COPY ({query}) TO '{output.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)")
            connection.execute(f"CREATE OR REPLACE TEMP VIEW monthly AS SELECT * FROM read_parquet('{output.as_posix()}')")
            quality = connection.execute("""SELECT count(*) AS raw_rows,
                count(*) FILTER(WHERE NOT time_in_scope) AS outside_source_month,
                count(*) FILTER(WHERE time_in_scope AND is_voided) AS voided_in_scope,
                count(*) FILTER(WHERE eligible_pickup AND NOT known_pickup) AS unknown_pickup,
                count(*) FILTER(WHERE demand_valid) AS demand_rows,
                count(*) FILTER(WHERE time_in_scope) AS in_scope_rows,
                count(*) FILTER(WHERE demand_valid AND fare_valid) AS fare_rows,
                count(*) FILTER(WHERE demand_valid AND efficiency_valid) AS efficiency_rows,
                count(*) FILTER(WHERE demand_valid AND tip_valid) AS tip_rows,
                count(*) FILTER(WHERE negative_amount) AS negative_amount,
                count(*) FILTER(WHERE extreme_amount) AS extreme_amount,
                count(*) FILTER(WHERE missing_amount) AS missing_amount,
                count(*) FILTER(WHERE bad_duration) AS bad_duration,
                count(*) FILTER(WHERE bad_distance) AS bad_distance,
                count(*) FILTER(WHERE bad_speed) AS bad_speed,
                count(*) FILTER(WHERE dst_efficiency_excluded) AS dst_efficiency_excluded,
                count(*) FILTER(WHERE any_quality_flag) AS flagged_rows FROM monthly""").fetchdf().iloc[0].astype(int).to_dict()
            names = [f'"{name}"' for name in pq.read_schema(raw).names]
            duplicates = connection.execute(f"SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) AS n FROM read_parquet('{raw.as_posix()}') GROUP BY {','.join(names)} HAVING count(*)>1)").fetchone()[0]
            quality["identical_field_extra_rows"] = int(duplicates)
            if quality["raw_rows"] != item["rows"]:
                raise ValueError("Full scan differs from Parquet footer")
        quality_rows.append({"source_month": month, **quality})
        month_cache[month] = {"source_sha256": item["sha256"], "code_hash": code_hash, "output_sha256": sha256(output), "quality": quality}
        write_json(cache_path, {"months": month_cache})
    csv(pd.DataFrame(quality_rows), "data_quality_monthly")
    connection.execute(f"CREATE OR REPLACE VIEW fact_trip AS SELECT * FROM read_parquet('{trip_folder.as_posix()}/*.parquet',union_by_name=TRUE)")
    query = """SELECT zone_id, CAST(pickup_hour AS DATE) AS date, hour(pickup_hour) AS hour, pickup_hour,
       count(*) AS trips,
       count(*) FILTER(WHERE fare_valid) AS fare_n,
       sum(CASE WHEN fare_valid THEN fare_amount ELSE 0 END) AS fare_sum,
       sum(CASE WHEN fare_valid THEN total_amount ELSE 0 END) AS total_charge_sum,
       count(*) FILTER(WHERE efficiency_valid) AS efficiency_n,
       sum(CASE WHEN efficiency_valid THEN distance_km ELSE 0 END) AS distance_km_sum,
       sum(CASE WHEN efficiency_valid THEN duration_min ELSE 0 END) AS duration_min_sum,
       sum(CASE WHEN efficiency_valid THEN speed_kmh ELSE 0 END) AS speed_kmh_sum,
       count(*) FILTER(WHERE tip_valid) AS tip_n,
       sum(CASE WHEN tip_valid THEN tip_amount ELSE 0 END) AS tip_sum,
       sum(CASE WHEN tip_valid THEN fare_amount ELSE 0 END) AS tip_fare_sum,
       count(*) FILTER(WHERE any_quality_flag) AS flagged_n
       FROM fact_trip WHERE demand_valid GROUP BY ALL"""
    connection.execute(f"CREATE OR REPLACE TABLE fact_zone_hour AS {query}")
    hourly = connection.execute("SELECT * FROM fact_zone_hour ORDER BY zone_id,pickup_hour").fetchdf()
    if hourly.trips.sum() != sum(row["demand_rows"] for row in quality_rows):
        raise ValueError("Trip / hourly count mismatch")
    hourly.to_parquet(ROOT / "data/processed/zone_hour_observed.parquet", index=False)
    csv(hourly.drop(columns="pickup_hour"), "fact_zone_hour")
    connection.execute("""CREATE OR REPLACE TABLE fact_route AS SELECT source_month AS month,zone_id,dropoff_zone_id,count(*) AS trips,
       count(*) FILTER(WHERE efficiency_valid) AS efficiency_n,
       sum(CASE WHEN efficiency_valid THEN duration_min ELSE 0 END) AS duration_min_sum
       FROM fact_trip WHERE demand_valid AND known_dropoff GROUP BY ALL""")
    csv(connection.execute("SELECT * FROM fact_route ORDER BY trips DESC").fetchdf(), "route_monthly")
    connection.close()
    write_json(ROOT / "data/processed/data_model_manifest.json", {"source_rows": sum(x["raw_rows"] for x in quality_rows), "demand_rows": int(hourly.trips.sum()), "observed_zone_hours": len(hourly), "raw_duplicate_policy": "Identical original fields counted within each source month; all retained because there is no unique trip ID.", "demand_rule": "pickup belongs to its source month, payment_type is not explicitly 6, PULocationID in 1..263; fare/duration anomalies do not delete the demand record", "dst_efficiency_rule": "Conservatively exclude the two transition days from time/speed denominators; counts are retained."})
