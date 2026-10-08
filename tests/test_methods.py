from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import ROOT, FEATURES, BASELINES, MONTHS
from src.features import zone_features,model_frame
from src.models import metrics,chronological_masks
from src.simulate import allocate
from src.prepare import require_complete_sources

@pytest.mark.parametrize("budget",[0,1,500,1000,2000,100000])
def test_allocation_conserves_budget_and_permutation(budget):
    rng=np.random.default_rng(42)
    zones=np.arange(1,264)
    weights=rng.lognormal(0,2,size=len(zones))
    assigned=allocate(weights,budget,zones)
    order=rng.permutation(len(zones))
    permuted=allocate(weights[order],budget,zones[order])
    assert assigned.sum()==budget and (assigned>=0).all()
    assert np.array_equal(assigned[order],permuted)

def test_zero_predictions_and_equal_remainders():
    assert allocate([0,0,0],2,[3,1,2]).tolist()==[0,1,1]
    assert allocate([1,1,1],5,[3,1,2]).tolist()==[1,2,2]

@pytest.mark.parametrize("weights,budget,zones",[([-1,2],3,[1,2]),([np.nan,2],3,[1,2]),([1,2],-1,[1,2]),([1,2],1.2,[1,2]),([1,2],3,[1,1])])
def test_invalid_allocation_rejected(weights,budget,zones):
    with pytest.raises(ValueError):allocate(weights,budget,zones)

def test_simulation_coverage_bounds():
    y=np.array([0,30,100])
    a=allocate([0,1,5],80,[1,2,3])
    served=np.minimum(y,a)
    assert served.sum()<=min(y.sum(),a.sum())
    assert np.array_equal((y-served)+served,y)
    assert np.array_equal((a-served)+served,a)

def test_metrics_hand_calculation_and_zero_denominator():
    result=metrics([0,10],[2,8])
    assert result["wape"]==pytest.approx(.4)
    assert result["mae"]==2 and result["rmse"]==2 and result["bias"]==0
    assert metrics([0,0],[1,0])["wape"] is None

def test_future_changes_do_not_change_past_features():
    index=pd.date_range("2025-01-01",periods=1400,freq="h")
    original=pd.Series(np.arange(len(index))%13,index=index)
    changed=original.copy();changed.iloc[1000:]=999
    a,b=zone_features(original,1),zone_features(changed,1)
    pd.testing.assert_frame_equal(a.loc[:1000,FEATURES+BASELINES],b.loc[:1000,FEATURES+BASELINES])
    assert a.loc[1000,"lag_1"]==original.iloc[999]
    assert a.loc[1000,"roll_mean_3"]==pytest.approx(original.iloc[997:1000].mean())

def test_dst_is_not_zero_or_arbitrarily_localized():
    index=pd.date_range("2025-01-01", "2026-01-01",freq="h",inclusive="left")
    result=zone_features(pd.Series(10,index=index),1).set_index("pickup_hour")
    for hour in ["2025-03-09 02:00","2025-11-02 01:00"]:
        time=pd.Timestamp(hour)
        assert result.loc[time,"dst_ambiguous"] and pd.isna(result.loc[time,"y"])
        assert not result.loc[time,"model_eligible"]
        assert not result.loc[time+pd.Timedelta(hours=1),"model_eligible"]
        assert pd.isna(result.loc[time+pd.Timedelta(hours=168),"weekly_naive"])
        assert pd.isna(result.loc[time+pd.Timedelta(hours=672),"four_week_mean"])
    assert result.loc["2025-12-15 10:00","model_eligible"]

def test_unobserved_valid_zone_hour_is_real_zero():
    index=pd.date_range("2025-01-01",periods=1000,freq="h")
    result=zone_features(pd.Series(0,index=index),1)
    assert result.loc[900,"y"]==0 and result.loc[900,"model_eligible"]

def test_fixed_category_universe_and_no_forbidden_features():
    assert not set(FEATURES)&{"y","actual_trips","fare_amount","duration_min","temperature_2m_mean","selected_prediction"}
    frame=pd.DataFrame({name:[1] for name in FEATURES})
    assert len(model_frame(frame).zone_id.cat.categories)==263

def test_time_splits_have_no_future_overlap():
    frame=pd.DataFrame({"pickup_hour":pd.date_range("2025-01-01", "2026-01-01",freq="h",inclusive="left")})
    for month in [9,10,11,12]:
        train,valid=chronological_masks(frame,month)
        assert not (train&valid).any()
        assert frame.loc[train,"pickup_hour"].max()<frame.loc[valid,"pickup_hour"].min()
        assert frame.loc[train,"pickup_hour"].dt.month.max()==month-1

def test_missing_month_stops_before_zero_filling():
    with pytest.raises(ValueError):require_complete_sources({"complete":False,"files":[]})
    with pytest.raises(ValueError):require_complete_sources({"complete":True,"files":[]})

def test_trip_quality_denominators_are_independent(tmp_path):
    n=7
    data={"VendorID":[1]*n,"tpep_pickup_datetime":[pd.Timestamp("2025-01-05 12:00")]*n,"tpep_dropoff_datetime":[pd.Timestamp("2025-01-05 12:15")]*n,"PULocationID":[161,161,264,161,161,161,161],"DOLocationID":[162]*n,"passenger_count":[1]*n,"RatecodeID":[1]*n,"payment_type":[1,1,1,6,2,1,1],"trip_distance":[2.,2.,2.,2.,2.,0.,2.],"fare_amount":[10.,-10.,10.,10.,10.,10.,10.],"total_amount":[15.,-15.,15.,15.,15.,15.,15.],"tip_amount":[2.,-2.,2.,2.,0.,2.,0.]}
    for column in ["extra","mta_tax","tolls_amount","improvement_surcharge","congestion_surcharge","airport_fee","cbd_congestion_fee"]:data[column]=[0.]*n
    source=tmp_path/"fixture.parquet"
    pq.write_table(pa.Table.from_pydict(data),source)
    query=(ROOT/"sql/01_trip_model.sql").read_text().format(month="2025-01",source_path=source.as_posix())
    output=duckdb.connect().execute(query).fetchdf()
    assert output.demand_valid.tolist()==[True,True,False,False,True,True,True]
    assert output.loc[1,"negative_amount"] and not output.loc[1,"fare_valid"]
    assert output.loc[1,"demand_valid"]
    assert not output.loc[4,"tip_valid"] and output.loc[4,"fare_valid"]
    assert output.loc[5,"demand_valid"] and not output.loc[5,"efficiency_valid"]
    assert output.loc[6,"tip_valid"] and output.loc[6,"tip_amount"]==0
