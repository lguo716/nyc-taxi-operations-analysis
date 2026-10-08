import pandas as pd
from .config import ROOT
from .utils import csv,write_json

SUMS=["trips","fare_n","fare_sum","total_charge_sum","efficiency_n","distance_km_sum","duration_min_sum","speed_kmh_sum","tip_n","tip_sum","tip_fare_sum","flagged_n"]

def derived(frame):
    frame=frame.copy()
    for name,num,den in [("avg_fare","fare_sum","fare_n"),("avg_total_charge","total_charge_sum","fare_n"),("avg_distance_km","distance_km_sum","efficiency_n"),("avg_duration_min","duration_min_sum","efficiency_n"),("avg_speed_kmh","speed_kmh_sum","efficiency_n"),("tip_rate","tip_sum","tip_fare_sum"),("flag_rate","flagged_n","trips")]:
        frame[name]=frame[num]/frame[den].replace(0,float("nan"))
    return frame

def analyze():
    hourly=pd.read_parquet(ROOT / "data/processed/zone_hour_observed.parquet")
    dates=pd.read_csv(ROOT / "reports/tables/dim_date.csv",parse_dates=["date"])
    zones=pd.read_csv(ROOT / "reports/tables/dim_zone.csv")
    joined=hourly.merge(dates,on="date",validate="many_to_one").merge(zones,on="zone_id",validate="many_to_one")
    for name,keys in [("monthly_metrics",["month_label"]),("daily_metrics",["date","month","weekday","day_type","weather_group","temperature_2m_mean","precipitation_sum","snowfall_sum"]),("hourly_profile",["hour","day_type"]),("zone_metrics",["zone_id","borough","zone","zone_label"]),("borough_metrics",["borough"]),("weekday_hour",["weekday","hour"])]:
        csv(derived(joined.groupby(keys,as_index=False,dropna=False)[SUMS].sum()),name)
    # Daily exposure denominators make weather comparisons comparable within month/weekday strata.
    daily=joined.groupby("date",as_index=False)[SUMS].sum().merge(dates,on="date",validate="one_to_one")
    strata=daily.groupby(["month","weekday","weather_group"],as_index=False).agg(days=("date","size"),trips=("trips","sum"),mean_daily_trips=("trips","mean"),std_daily_trips=("trips","std"))
    csv(strata,"weather_strata")
    overall=derived(pd.DataFrame([hourly[SUMS].sum().to_dict()]))
    csv(overall,"kpi_summary")
    quality=pd.read_csv(ROOT / "reports/tables/data_quality_monthly.csv")
    totals=quality.drop(columns="source_month").sum()
    checks=[{"check":"source_rows_reconciled","actual":int(totals.raw_rows),"expected":int(totals.outside_source_month+totals.voided_in_scope+totals.unknown_pickup+totals.demand_rows),"passed":bool(totals.raw_rows==totals.outside_source_month+totals.voided_in_scope+totals.unknown_pickup+totals.demand_rows)}, {"check":"hourly_demand_reconciled","actual":int(hourly.trips.sum()),"expected":int(totals.demand_rows),"passed":bool(hourly.trips.sum()==totals.demand_rows)}]
    write_json(ROOT / "reports/reconciliation.json",{"checks":checks,"passed":all(x["passed"] for x in checks)})
