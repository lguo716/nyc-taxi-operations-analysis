import json
import logging
import numpy as np
import pandas as pd
import duckdb
import lightgbm as lgb

from .config import ROOT,FEATURES,BASELINES,MONTHS,LABELS
from .utils import read_json,write_json,sha256,csv,utc_now
from .prepare import require_complete_sources,connect
from .features import model_frame

def verify():
    checks=[]
    def check(name,passed,actual=None,expected=None):
        checks.append({"check":name,"passed":bool(passed),"actual":actual,"expected":expected})
    manifest=read_json(ROOT/"data/source_manifest.json")
    sources=require_complete_sources(manifest)
    for relative,item in sources.items():
        check(f"source_identity:{relative}",sha256(ROOT/relative)==item["sha256"] and (ROOT/relative).stat().st_size==item["bytes"])
    quality=pd.read_csv(ROOT/"reports/tables/data_quality_monthly.csv")
    check("12_complete_months",quality.source_month.tolist()==MONTHS)
    check("footer_vs_full_scan",int(quality.raw_rows.sum())==sum(x["rows"] for x in sources.values() if x["kind"]=="trip"))
    check("exclusions_partition",bool((quality.raw_rows==quality.outside_source_month+quality.voided_in_scope+quality.unknown_pickup+quality.demand_rows).all()))
    connection=connect()
    totals=connection.execute((ROOT/"sql/02_quality_reconciliation.sql").read_text()).fetchdf().iloc[0]
    for source_name,quality_name in [("raw_rows","raw_rows"),("demand_rows","demand_rows"),("fare_n","fare_rows"),("efficiency_n","efficiency_rows"),("tip_n","tip_rows")]:
        check(f"sql_{source_name}",int(totals[source_name])==int(quality[quality_name].sum()),int(totals[source_name]),int(quality[quality_name].sum()))
    sql_monthly=connection.execute((ROOT/"sql/03_business_metrics.sql").read_text()).fetchdf()
    csv(sql_monthly,"sql_monthly_verification")
    monthly=pd.read_csv(ROOT/"reports/tables/monthly_metrics.csv")
    for column in ["trips","fare_n","fare_sum","total_charge_sum"]:
        check(f"sql_monthly_{column}",np.allclose(sql_monthly[column],monthly[column],rtol=1e-12,atol=.0001))
    observed=pd.read_parquet(ROOT/"data/processed/zone_hour_observed.parquet")
    sql_hourly=connection.execute((ROOT/"sql/04_zone_hour.sql").read_text()).fetchdf()
    observed=observed.sort_values(["zone_id","pickup_hour"])
    check("independent_sql_hourly",np.array_equal(sql_hourly.trips.to_numpy(),observed.trips.to_numpy()))
    frame=pd.read_parquet(ROOT/"data/processed/features.parquet")
    check("grid_unique",not frame.duplicated(["zone_id","pickup_hour"]).any())
    check("grid_263_zones",frame.zone_id.nunique()==263 and len(frame)==263*8760)
    check("grid_total_reconciles",int(frame.actual_trips.sum())==int(quality.demand_rows.sum()))
    check("dst_not_valid",not frame.loc[frame.dst_ambiguous,"model_eligible"].any())
    check("eligible_features_finite",np.isfinite(frame.loc[frame.model_eligible,FEATURES+BASELINES+["y"]].to_numpy()).all())
    check("features_only_allowlist",read_json(ROOT/"models/feature_protocol.json")["features"]==FEATURES)
    selection=read_json(ROOT/"models/model_selection.json")
    scores=pd.read_csv(ROOT/"reports/tables/validation_metrics.csv").groupby("model").wape.mean()
    order=[*BASELINES,"lgbm_31","lgbm_63"]
    check("validation_selects_winner",selection["selected_model"]==min(order,key=lambda x:(scores[x],order.index(x))))
    for split in selection["splits"]:
        check(f"chronology_fold_{split['validation_month']}",pd.Timestamp(split["train_end"])<pd.Timestamp(split["validation_start"]))
    predictions=pd.read_parquet(ROOT/"data/processed/test_predictions.parquet")
    check("test_only_december",set(predictions.pickup_hour.dt.month)=={12})
    check("test_never_selects_model",selection["test_used_for_selection"] is False)
    features=frame.loc[frame.model_eligible & (frame.month==12)].sort_values(["pickup_hour","zone_id"]).reset_index(drop=True)
    check("test_row_alignment",predictions[["pickup_hour","zone_id"]].reset_index(drop=True).equals(features[["pickup_hour","zone_id"]]))
    for name in BASELINES:
        check(f"baseline_recalculation_{name}",np.allclose(features[name],predictions[name],rtol=0,atol=0))
    for name in ["lgbm_31","lgbm_63"]:
        model=lgb.Booster(model_file=str(ROOT/f"models/{name}_final.txt"))
        recalculated=np.maximum(model.predict(model_frame(features)),0)
        check(f"independent_model_reload_{name}",np.allclose(recalculated,predictions[name],rtol=1e-12,atol=1e-10))
    connection.execute(f"CREATE OR REPLACE TEMP VIEW predictions AS SELECT * FROM read_parquet('{(ROOT/'data/processed/test_predictions.parquet').as_posix()}')")
    metric=connection.execute((ROOT/"sql/05_forecast_metrics.sql").read_text()).fetchdf().iloc[0]
    test=pd.read_csv(ROOT/"reports/tables/test_metrics.csv").query("selected==1").iloc[0]
    for name in ["n","actual_sum","wape","mae","rmse"]:
        check(f"sql_test_{name}",np.isclose(metric[name],test[name],rtol=1e-10,atol=1e-8))
    sim=pd.read_parquet(ROOT/"data/processed/simulation_detail.parquet")
    group=sim.groupby(["date","hour","budget","strategy"]).allocation.sum().reset_index()
    check("simulation_hourly_budget_conserved",(group.allocation==group.budget).all())
    check("simulation_nonnegative",(sim[["allocation","served","uncovered","idle"]]>=0).all().all())
    check("simulation_demand_conserved",(sim.served+sim.uncovered==sim.actual).all())
    check("simulation_capacity_conserved",(sim.served+sim.idle==sim.allocation).all())
    check("simulation_coverage_bounded",(sim.served<=sim.actual).all() and (sim.served<=sim.allocation).all())
    shape=read_json(ROOT/"powerbi/taxi_zones.geojson")
    keys=[int(x["properties"]["zone_key"]) for x in shape["features"]]
    check("map_unique_keys",len(keys)==len(set(keys)))
    check("map_covers_all_physical_zones",set(keys)==set(range(1,264)))
    weather=pd.read_csv(ROOT/"reports/tables/dim_date.csv")
    check("365_unique_calendar_weather_dates",len(weather)==365 and weather.date.nunique()==365)
    check("weather_complete_variables",not weather[["temperature_2m_mean","precipitation_sum","snowfall_sum"]].isna().any().any())
    connection.close()
    result={"verified_at":utc_now(),"passed":all(x["passed"] for x in checks),"passed_count":sum(x["passed"] for x in checks),"total_count":len(checks),"checks":checks,"reproducibility_note":"Independent process recomputes source-to-hour SQL, reloads saved final models, re-predicts the complete December test set, recalculates metrics and simulation identities."}
    write_json(ROOT/"reports/artifact_verification.json",result)
    logging.info("Artifact checks %s/%s",result["passed_count"],len(checks))
    if not result["passed"]:
        raise ValueError("Artifact verification failed: "+str([x["check"] for x in checks if not x["passed"]]))
