import pandas as pd
from .config import ROOT, LABELS, BASELINES
from .models import metrics
from .utils import csv, read_json

def evaluate():
    frame = pd.read_parquet(ROOT / "data/processed/test_predictions.parquet")
    zones = pd.read_csv(ROOT / "reports/tables/dim_zone.csv")
    frame = frame.merge(zones[["zone_id","borough","zone_label"]],on="zone_id",validate="many_to_one")
    frame["date"] = frame.pickup_hour.dt.strftime("%Y-%m-%d")
    frame["hour"] = frame.pickup_hour.dt.hour
    selection = read_json(ROOT / "models/model_selection.json")
    records, groups, daily, by_zone = [],[],[],[]
    for name in [*BASELINES,"lgbm_31","lgbm_63"]:
        records.append({"split":"test","month":12,"model":name,"model_label":LABELS[name],"selected":int(name==selection["selected_model"]),**metrics(frame.y,frame[name])})
        for group in ["borough","hour"]:
            for key, part in frame.groupby(group):
                groups.append({"model":name,"model_label":LABELS[name],"dimension":group,"group":str(key),**metrics(part.y,part[name])})
        for date, part in frame.groupby("date"):
            daily.append({"date":date,"model":name,"model_label":LABELS[name],**metrics(part.y,part[name])})
        for zone,part in frame.groupby("zone_id"):
            by_zone.append({"zone_id":zone,"model":name,"model_label":LABELS[name],**metrics(part.y,part[name])})
    csv(pd.DataFrame(records),"test_metrics")
    csv(pd.DataFrame(groups),"test_errors_by_group")
    csv(pd.DataFrame(daily),"test_daily_metrics")
    csv(pd.DataFrame(by_zone),"test_zone_metrics")
    hourly = frame[["zone_id","date","hour","y","selected_prediction"]].rename(columns={"y":"actual","selected_prediction":"predicted"})
    hourly["absolute_error"] = (hourly.predicted-hourly.actual).abs()
    hourly["squared_error"] = (hourly.predicted-hourly.actual)**2
    csv(hourly,"forecast_hourly")
    frame["date"] = pd.to_datetime(frame.date)
    csv(pd.DataFrame({"model":[*BASELINES,"lgbm_31","lgbm_63"],"model_label":[LABELS[x] for x in [*BASELINES,"lgbm_31","lgbm_63"]]}),"dim_model")
