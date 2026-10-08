import logging
import numpy as np
import pandas as pd

from .config import ROOT, FEATURES, BASELINES, HOLIDAYS, TZ
from .utils import csv, write_json

def zone_features(series, zone_id):
    """Features for target [t,t+1h); only completed hours strictly before t."""
    index = pd.DatetimeIndex(series.index)
    ambiguous = index.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT").isna()
    y = series.astype("float32").copy()
    y.loc[ambiguous] = np.nan
    result = pd.DataFrame({"pickup_hour": index, "zone_id": zone_id, "actual_trips": series.to_numpy(dtype="int32"), "y": y.to_numpy(), "dst_ambiguous": ambiguous})
    result["hour"] = index.hour.astype("int8")
    result["weekday"] = index.dayofweek.astype("int8")
    result["month"] = index.month.astype("int8")
    result["is_weekend"] = (index.dayofweek>=5).astype("int8")
    result["is_holiday"] = index.strftime("%Y-%m-%d").isin(HOLIDAYS).astype("int8")
    for lag in [1,2,24,168]:
        result[f"lag_{lag}"] = y.shift(lag).to_numpy()
    for window in [3,24,168]:
        # min_periods=window intentionally invalidates windows touching a DST ambiguity.
        result[f"roll_mean_{window}"] = y.shift(1).rolling(window, min_periods=window).mean().to_numpy(dtype="float32")
    for window in [24,168]:
        result[f"roll_std_{window}"] = y.shift(1).rolling(window, min_periods=window).std(ddof=0).to_numpy(dtype="float32")
    result["daily_naive"] = y.shift(24).to_numpy()
    result["weekly_naive"] = y.shift(168).to_numpy()
    result["four_week_mean"] = pd.concat([y.shift(168*k) for k in range(1,5)],axis=1).mean(axis=1,skipna=False).to_numpy(dtype="float32")
    result["model_eligible"] = result[FEATURES + BASELINES + ["y"]].notna().all(axis=1)
    return result

def features():
    observed = pd.read_parquet(ROOT / "data/processed/zone_hour_observed.parquet")
    zones = pd.read_csv(ROOT / "reports/tables/dim_zone.csv").query("1<=zone_id<=263")
    index = pd.date_range("2025-01-01", "2026-01-01",freq="h",inclusive="left")
    frames = []
    for zone in zones.zone_id:
        counts = observed.loc[observed.zone_id==zone].set_index("pickup_hour").trips.reindex(index,fill_value=0)
        frames.append(zone_features(counts,int(zone)))
    result = pd.concat(frames,ignore_index=True)
    result["zone_id"] = result.zone_id.astype("int16")
    result.to_parquet(ROOT / "data/processed/features.parquet",index=False)
    summary = result.groupby("month",as_index=False).agg(grid_rows=("y","size"),eligible_rows=("model_eligible","sum"),dst_ambiguous_rows=("dst_ambiguous","sum"),trips=("actual_trips","sum"))
    csv(summary,"feature_coverage")
    write_json(ROOT / "models/feature_protocol.json", {"target": "recorded pickup count in [t,t+1h), predicted at t", "features": FEATURES, "excluded_features": ["target hour orders", "fares", "duration", "dropoff outcomes", "weather reanalysis", "future weather"], "time_zone": TZ, "dst": "Ambiguous/nonexistent local hours are NaN. Targets and every lag/rolling/baseline window touching these NaNs are excluded, using one common evaluation universe.", "first_eligible_hour": str(result.loc[result.model_eligible,"pickup_hour"].min()), "grid_rows": len(result), "eligible_rows": int(result.model_eligible.sum()), "assumption": "Retrospective rolling one-hour evaluation assumes previous completed pickup-hour counts available at t; monthly publisher data cannot establish real-time arrival latency."})
    logging.info("Feature grid %s rows; eligible %s",len(result),result.model_eligible.sum())

def model_frame(frame):
    x = frame[FEATURES].copy()
    # Fixed published zone universe, not a category dictionary learned from future outcomes.
    x["zone_id"] = pd.Categorical(x.zone_id,categories=range(1,264))
    return x
