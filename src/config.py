from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
SEED = 42
TZ = "America/New_York"
FEATURES = ["zone_id", "hour", "weekday", "month", "is_weekend", "is_holiday", "lag_1", "lag_2", "lag_24", "lag_168", "roll_mean_3", "roll_mean_24", "roll_mean_168", "roll_std_24", "roll_std_168"]
BASELINES = ["daily_naive", "weekly_naive", "four_week_mean"]
LABELS = {"daily_naive": "前一天同小时", "weekly_naive": "前一周同小时", "four_week_mean": "四周同星期同小时均值", "lgbm_31": "LightGBM（31叶）", "lgbm_63": "LightGBM（63叶）"}
HOLIDAYS = {"2025-01-01": "New Year's Day", "2025-01-20": "Martin Luther King Jr. Day", "2025-02-17": "Washington's Birthday", "2025-05-26": "Memorial Day", "2025-06-19": "Juneteenth", "2025-07-04": "Independence Day", "2025-09-01": "Labor Day", "2025-10-13": "Columbus Day", "2025-11-11": "Veterans Day", "2025-11-27": "Thanksgiving Day", "2025-12-25": "Christmas Day"}

def ensure_dirs():
    for directory in ["data/raw", "data/reference", "data/processed", "data/tmp", "sql", "models", "reports/tables", "reports/figures/powerbi", "docs", "notebooks", "tests", "powerbi", "logs"]:
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
