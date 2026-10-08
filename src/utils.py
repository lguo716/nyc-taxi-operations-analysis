import hashlib
import json
import logging
from datetime import datetime, timezone

from .config import ROOT, ensure_dirs

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def configure_logging(stage):
    ensure_dirs()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.FileHandler(ROOT / "logs" / f"{stage}.log", encoding="utf-8"), logging.StreamHandler()], force=True)

def csv(frame, name):
    frame.to_csv(ROOT / "reports/tables" / f"{name}.csv", index=False, encoding="utf-8-sig", float_format="%.15g")
