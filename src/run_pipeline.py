import argparse
import importlib
import logging
import time

from .config import ROOT,SEED
from .utils import configure_logging,read_json,write_json,utc_now

STAGES={"download":"download","prepare":"prepare","analyze":"analyze","features":"features","train":"models","evaluate":"evaluate","simulate":"simulate","report":"reporting","verify":"verify"}

def main():
    parser=argparse.ArgumentParser(description="NYC Yellow Taxi full-year analysis pipeline")
    parser.add_argument("--stage",choices=["all",*STAGES],default="all")
    parser.add_argument("--seed",type=int,default=SEED)
    args=parser.parse_args()
    configure_logging(args.stage)
    write_json(ROOT / "run_config.json",{"year":2025,"months":12,"seed":args.seed,"forecast_horizon_hours":1,"validation_months":[9,10,11],"test_month":12,"simulation_budgets":[500,1000,2000],"run_at":utc_now()})
    stages=list(STAGES) if args.stage=="all" else [args.stage]
    timing_path=ROOT / "reports/stage_timings.json"
    timings=read_json(timing_path) if timing_path.exists() else {}
    for stage in stages:
        logging.info("Stage %s started",stage)
        start=time.perf_counter()
        module=importlib.import_module(f"src.{STAGES[stage]}")
        function=getattr(module,stage)
        function(seed=args.seed) if stage=="train" else function()
        timings[stage]={"seconds":round(time.perf_counter()-start,3),"finished_at":utc_now()}
        write_json(timing_path,timings)
        logging.info("Stage %s completed %.1f seconds",stage,timings[stage]["seconds"])

if __name__=="__main__":
    main()
