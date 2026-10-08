import numpy as np
import pandas as pd

from .config import ROOT
from .utils import csv,read_json

def allocate(weights,budget,zone_ids):
    """Hamilton largest remainder, deterministic zone-ID tie breaks, exact conservation."""
    weights,zone_ids=np.asarray(weights,dtype=float),np.asarray(zone_ids,dtype=int)
    if len(weights)==0 or len(weights)!=len(zone_ids) or len(np.unique(zone_ids))!=len(zone_ids):
        raise ValueError("Unique zone universe required")
    if not isinstance(budget,(int,np.integer)) or budget<0 or not np.isfinite(weights).all() or (weights<0).any():
        raise ValueError("Finite nonnegative weights and integer budget required")
    if weights.sum()==0:
        weights=np.ones(len(weights))
    exact=weights/weights.sum()*budget
    integer=np.floor(exact).astype(np.int64)
    remaining=budget-int(integer.sum())
    order=np.lexsort((zone_ids,-(exact-integer)))
    integer[order[:remaining]]+=1
    assert integer.sum()==budget and (integer>=0).all()
    return integer

def simulate():
    frame=pd.read_parquet(ROOT / "data/processed/test_predictions.parquet").sort_values(["pickup_hour","zone_id"])
    records=[]
    strategies={"uniform":"均匀分配","history":"四周历史均值分配","forecast":"选定预测方案分配"}
    for time,part in frame.groupby("pickup_hour",sort=True):
        y=part.y.to_numpy()
        for budget in [500,1000,2000]:
            for strategy,label in strategies.items():
                weights=np.ones(len(part)) if strategy=="uniform" else part.four_week_mean.to_numpy() if strategy=="history" else part.selected_prediction.to_numpy()
                allocation=allocate(weights,budget,part.zone_id.to_numpy())
                served=np.minimum(y,allocation)
                for zone,actual,pred,a,s in zip(part.zone_id,y,weights,allocation,served):
                    records.append({"date":time.strftime("%Y-%m-%d"),"hour":time.hour,"zone_id":int(zone),"budget":budget,"strategy":strategy,"strategy_label":label,"actual":int(actual),"allocation":int(a),"served":int(s),"uncovered":int(actual-s),"idle":int(a-s)})
    details=pd.DataFrame(records)
    details.to_parquet(ROOT / "data/processed/simulation_detail.parquet",index=False)
    daily=details.groupby(["date","budget","strategy","strategy_label"],as_index=False)[["actual","allocation","served","uncovered","idle"]].sum()
    csv(daily,"simulation_daily")
    zone=details.groupby(["zone_id","budget","strategy","strategy_label"],as_index=False)[["actual","allocation","served","uncovered","idle"]].sum()
    csv(zone,"simulation_zone")
    summary=details.groupby(["budget","strategy","strategy_label"],as_index=False)[["actual","allocation","served","uncovered","idle"]].sum()
    summary["coverage"]=summary.served/summary.actual
    summary["utilization"]=summary.served/summary.allocation
    csv(summary,"simulation_summary")
    csv(pd.DataFrame({"budget":[500,1000,2000],"budget_label":["500 名额/小时","1,000 名额/小时","2,000 名额/小时"]}),"dim_budget")
    csv(pd.DataFrame({"strategy":list(strategies),"strategy_label":list(strategies.values())}),"dim_strategy")
