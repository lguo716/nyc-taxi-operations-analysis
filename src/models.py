import gc
import logging
import numpy as np
import pandas as pd
import lightgbm as lgb

from .config import ROOT, FEATURES, BASELINES, LABELS, SEED
from .features import model_frame
from .utils import csv, write_json

def metrics(y,pred):
    y, pred = np.asarray(y,dtype=float), np.asarray(pred,dtype=float)
    if len(y)==0 or not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise ValueError("Metrics need nonempty finite, aligned values")
    error = pred-y
    return {"n": len(y), "actual_sum": float(y.sum()), "prediction_sum":float(pred.sum()), "absolute_error_sum":float(np.abs(error).sum()), "squared_error_sum":float(np.square(error).sum()), "wape":float(np.abs(error).sum()/y.sum()) if y.sum()>0 else None, "mae":float(np.abs(error).mean()), "rmse":float(np.sqrt(np.square(error).mean())), "bias":float(error.mean())}

def chronological_masks(frame,month):
    start = pd.Timestamp(f"2025-{month:02d}-01")
    end = start + pd.offsets.MonthBegin(1)
    return frame.pickup_hour<start, (frame.pickup_hour>=start)&(frame.pickup_hour<end)

def train(seed=SEED):
    frame = pd.read_parquet(ROOT / "data/processed/features.parquet")
    frame = frame.loc[frame.model_eligible].sort_values(["pickup_hour","zone_id"]).reset_index(drop=True)
    x = model_frame(frame)
    records, fold_predictions, splits = [],[],[]
    params = {"objective":"poisson", "metric":"l1", "learning_rate":0.05, "n_estimators":2000, "min_child_samples":40, "max_bin":127, "n_jobs":4, "random_state":seed, "deterministic":True, "force_col_wise":True, "verbosity":-1}
    for month in [9,10,11]:
        training, validation = chronological_masks(frame,month)
        splits.append({"validation_month":month,"train_n":int(training.sum()),"validation_n":int(validation.sum()),"train_end":str(frame.loc[training,"pickup_hour"].max()),"validation_start":str(frame.loc[validation,"pickup_hour"].min()),"validation_end":str(frame.loc[validation,"pickup_hour"].max())})
        output = frame.loc[validation,["pickup_hour","zone_id","y",*BASELINES]].copy()
        output["fold"] = month
        for name in BASELINES:
            records.append({"split":"validation","month":month,"model":name,"model_label":LABELS[name],"best_iteration":None,**metrics(output.y,output[name])})
        for leaves in [31,63]:
            name = f"lgbm_{leaves}"
            logging.info("Training %s validation month=%s train=%s valid=%s",name,month,training.sum(),validation.sum())
            model = lgb.LGBMRegressor(**params,num_leaves=leaves)
            model.fit(x.loc[training],frame.loc[training,"y"],eval_set=[(x.loc[validation],frame.loc[validation,"y"])],eval_metric="l1",callbacks=[lgb.early_stopping(100,first_metric_only=True,verbose=False)],categorical_feature=["zone_id"])
            output[name] = np.maximum(model.predict(x.loc[validation]),0)
            records.append({"split":"validation","month":month,"model":name,"model_label":LABELS[name],"best_iteration":int(model.best_iteration_),**metrics(output.y,output[name])})
            model.booster_.save_model(str(ROOT / "models" / f"{name}_validation_{month}.txt"))
            csv(pd.DataFrame({"feature":FEATURES,"gain":model.booster_.feature_importance(importance_type="gain"),"model":name,"fold":month}),f"feature_importance_{name}_{month}")
            del model
            gc.collect()
        fold_predictions.append(output)
        csv(pd.DataFrame(records),"validation_metrics")
    result = pd.DataFrame(records)
    # Stable preference for simpler baseline when mean WAPE is exactly equal.
    order = [*BASELINES,"lgbm_31","lgbm_63"]
    scores = result.groupby("model").wape.mean()
    selected = min(order,key=lambda name:(scores[name],order.index(name)))
    iterations = {name:int(np.median(result.loc[result.model==name,"best_iteration"].dropna())) for name in ["lgbm_31","lgbm_63"]}
    protocol = {"seed":seed,"selected_model":selected,"selected_label":LABELS[selected],"selection_metric":"equal-weight mean WAPE over Sep, Oct, Nov","validation_scores":{name:float(scores[name]) for name in order},"refit_iterations":iterations,"test_month":"2025-12","splits":splits,"params":params,"test_used_for_selection":False}
    write_json(ROOT / "models/model_selection.json",protocol)
    pd.concat(fold_predictions,ignore_index=True).to_parquet(ROOT / "data/processed/validation_predictions.parquet",index=False)
    training, testing = chronological_masks(frame,12)
    output = frame.loc[testing,["pickup_hour","zone_id","y",*BASELINES]].copy()
    for leaves in [31,63]:
        name = f"lgbm_{leaves}"
        refit_params = {**params,"n_estimators":iterations[name],"num_leaves":leaves}
        model = lgb.LGBMRegressor(**refit_params)
        logging.info("Refit %s on Jan-Nov, fixed %s rounds",name,iterations[name])
        model.fit(x.loc[training],frame.loc[training,"y"],categorical_feature=["zone_id"])
        output[name] = np.maximum(model.predict(x.loc[testing]),0)
        model.booster_.save_model(str(ROOT / "models" / f"{name}_final.txt"))
        csv(pd.DataFrame({"feature":FEATURES,"gain":model.booster_.feature_importance(importance_type="gain"),"model":name}),f"feature_importance_{name}_final")
        del model
        gc.collect()
    output["selected_prediction"] = output[selected]
    output.to_parquet(ROOT / "data/processed/test_predictions.parquet",index=False)
    write_json(ROOT / "models/training_config.json",protocol)
    logging.info("Selected %s; test rows=%s",selected,len(output))
