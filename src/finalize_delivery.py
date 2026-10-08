"""Record the already performed native UI review and verify delivery identities."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd
from PIL import Image

from .config import ROOT
from .utils import read_json, sha256, utc_now, write_json


def main():
    desktop = read_json(ROOT / "powerbi/desktop_final_state.json")
    instance = desktop["instances"][0]
    assert Path(instance["currentFilePath"]).resolve() == (ROOT / "powerbi/nyc_taxi_operations.pbix").resolve()
    assert instance["hasUnsavedChanges"] is False
    dax = read_json(ROOT / "powerbi/desktop_verification.json")
    assert dax["passed"] is True
    for file in ["artifact_verification.json", "notebook_verification.json", "reproducibility_verification.json"]:
        assert read_json(ROOT / "reports" / file)["passed"] is True
    suites = ET.parse(ROOT / "reports/test_results.xml").getroot().iter("testsuite")
    suites = list(suites)
    assert sum(int(s.attrib["tests"]) for s in suites) == 21
    assert all(int(s.attrib["failures"]) + int(s.attrib["errors"]) == 0 for s in suites)

    checks = []

    def observed(check, file, expected):
        text = (ROOT / "powerbi" / file).read_text(encoding="utf-8")
        passed = expected in text
        checks.append({"check": check, "passed": passed, "expected_display": expected, "evidence": "powerbi/" + file})
        assert passed, check

    zones = pd.read_csv(ROOT / "reports/tables/zone_metrics.csv")
    jfk = zones.query("zone_id == 132").iloc[0]
    for label, value in [
        ("Trips", f"Trips {int(jfk.trips):,}"),
        ("Distance", f"平均里程 / 公里 {jfk.avg_distance_km:.2f}"),
        ("Speed", f"平均行程速度 / km/h {jfk.avg_speed_kmh:.2f}"),
        ("Efficiency N", f"效率指标有效记录数 {int(jfk.efficiency_n):,}"),
        ("Flag Rate", f"有效需求记录标记率 {jfk.flag_rate:.2%}"),
    ]:
        observed("map132." + label, "map_interaction.txt", value)
    sim = pd.read_csv(ROOT / "reports/tables/simulation_summary.csv")
    for budget in [500, 1000, 2000]:
        part = sim.query("budget == @budget")
        forecast = part.query("strategy == 'forecast'").iloc[0]
        history = part.query("strategy == 'history'").iloc[0]
        for label, value in [
            ("Served", f"预测方案模拟覆盖记录 {int(forecast.served):,}"),
            ("Idle", f"预测方案闲置名额 {int(forecast.idle):,}"),
            ("Advantage", f"相对历史方案多覆盖记录 {int(forecast.served-history.served):,}"),
            ("Coverage", f"预测方案模拟覆盖率 {forecast.coverage:.2%}"),
        ]:
            observed(f"budget{budget}." + label, f"budget{budget}_interaction.txt", value)
    january = pd.read_csv(ROOT / "reports/tables/monthly_metrics.csv").query("month_label == '2025-01'").iloc[0]
    for label, value in [
        ("Trips", f"有效区域上车记录 {int(january.trips):,}"),
        ("Fare", f"平均计价车费 ${january.avg_fare:.2f}"),
        ("Tip Rate", f"银行卡小费率 {january.tip_rate:.2%}"),
    ]:
        observed("reopened_pbix.january." + label, "pbix_january_interaction.txt", value)
    geometry = read_json(ROOT / "powerbi/taxi_zones.geojson")
    geo_keys = {int(f["properties"]["zone_key"]) for f in geometry["features"]}
    assert geo_keys == set(range(1, 264))
    assert len(geometry["features"]) == 263
    checks.append({"check": "map_keys", "passed": True, "matched_keys": 263, "unknown_mapped": False})
    screenshots = []
    review_notes = {
        "overview": "全年总量、费用/时长/小费卡片与月/小时/天气/日期分组均正常显示。",
        "regions": "本地纽约区域边界及渐变热度正常；中文表头、有效分母和独立源质量口径明确。",
        "forecast": "选定模型及误差卡片、五方案比较、实际/预测趋势、地图和小时误差均可见。",
        "dispatch": "默认1000名额；三策略曲线及覆盖/未覆盖/闲置矩阵与真实模拟一致。",
    }
    for page, note in review_notes.items():
        file = ROOT / f"reports/figures/powerbi/report_{page}.png"
        with Image.open(file) as img:
            width, height = img.size
        assert width >= 1600 and height >= 900
        screenshots.append({"page": page, "file": file.relative_to(ROOT).as_posix(), "width": width, "height": height,
                            "manual_visual_review": "passed", "review_note": note, "source": "reopened_and_refreshed_PBIX"})
    write_json(ROOT / "powerbi/ui_verification.json", {"verified_at": utc_now(), "passed": True,
               "desktop_pid": instance["pid"], "checks": checks, "screenshots": screenshots,
               "native_interaction_scope": "Map and all three budgets tested before PBIX conversion; January interaction and DAX retested after independent PBIX reopen and refresh."})

    documents = [ROOT / "README.md", *ROOT.glob("docs/*.md"), *ROOT.glob("reports/*.md"), ROOT / "powerbi/README.md"]
    missing = []
    for doc in documents:
        for target in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            link = target.split("#")[0]
            if link and not link.startswith(("http:", "https:", "mailto:")) and not (doc.parent / link).exists():
                if link != "delivery_manifest.json":
                    missing.append({"document": doc.relative_to(ROOT).as_posix(), "target": target})
    assert not missing, missing
    paths = {ROOT / "README.md", ROOT / "requirements.txt", ROOT / "NOTICE.md", ROOT / "run_config.json", ROOT / "data/source_manifest.json"}
    for folder in ["src", "tests", "sql", "docs", "notebooks", "models", "reports", "logs", "powerbi"]:
        paths.update(p for p in (ROOT / folder).rglob("*") if p.is_file()
                     and not any(part in {"node_modules", "__pycache__", ".pbi"} for part in p.relative_to(ROOT).parts)
                     and p.name not in {"delivery_manifest.json", "validation_offline.json"})
    paths.update(ROOT / "data/processed" / name for name in ["test_predictions.parquet", "validation_predictions.parquet", "simulation_detail.parquet"])
    identities = [{"file": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in sorted(paths)]
    write_json(ROOT / "reports/delivery_manifest.json", {"generated_at": utc_now(), "project": str(ROOT),
               "scope": "Local source, reports, editable Power BI artifacts and retained predictions; raw source identities are in data/source_manifest.json.",
               "files": identities, "count": len(identities), "link_check": "passed",
               "required_acceptance": "passed", "additional_static_cli_validation": "failed; see reports/project_acceptance.md"})
    print(f"Delivery verified: {len(checks)} UI/data checks, 4 reviewed screenshots, {len(identities)} artifact identities")


if __name__ == "__main__":
    main()
