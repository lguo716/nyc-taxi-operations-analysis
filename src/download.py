"""Fetch publisher data with Windows-native TLS, resume, and verified local identity."""
import logging
import csv
import io
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
import urllib.request
import zipfile

import pyarrow.parquet as pq
import shapefile

from .config import ROOT, MONTHS, ensure_dirs
from .utils import read_json, write_json, sha256, utc_now

def fetch(url, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl:
        result = subprocess.run([curl, "--fail", "--location", "--silent", "--show-error", "--retry", "4", "--retry-delay", "2", "--connect-timeout", "30", "--max-time", "900", "--continue-at", "-", "--output", str(partial), url], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f"Download failed for {url}: {result.stderr[-1200:]}")
    else:
        for attempt in range(4):
            try:
                offset = partial.stat().st_size if partial.exists() else 0
                request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-", "User-Agent": "nyc-taxi-portfolio/1.0"})
                with urllib.request.urlopen(request, timeout=180) as response:
                    resume = offset > 0 and response.status == 206
                    if resume and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Unexpected Content-Range")
                    with partial.open("ab" if resume else "wb") as output:
                        shutil.copyfileobj(response, output, length=1024 * 1024)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2)
    if not partial.exists() or not partial.stat().st_size:
        raise ValueError(f"Empty source {url}")
    partial.replace(target)

def download():
    ensure_dirs()
    manifest_path = ROOT / "data/source_manifest.json"
    previous = read_json(manifest_path) if manifest_path.exists() else {"files": []}
    old = {item["relative_path"]: item for item in previous["files"]}
    files = []
    entries = [(f"data/raw/yellow_tripdata_{month}.parquet", f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{month}.parquet", "trip") for month in MONTHS]
    entries += [("data/reference/taxi_zone_lookup.csv", "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv", "lookup"), ("data/reference/taxi_zones.zip", "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip", "boundary")]
    weather_query = urlencode({"latitude": 40.7812, "longitude": -73.9665, "start_date": "2025-01-01", "end_date": "2025-12-31", "daily": "temperature_2m_mean,precipitation_sum,snowfall_sum,wind_speed_10m_max", "timezone": "America/New_York", "models": "era5"})
    entries.append(("data/reference/weather_2025.json", "https://archive-api.open-meteo.com/v1/archive?" + weather_query, "weather"))
    for relative, url, kind in entries:
        target = ROOT / relative
        if target.exists():
            checksum = sha256(target)
            if relative in old and (checksum != old[relative]["sha256"] or target.stat().st_size != old[relative]["bytes"]):
                raise ValueError(f"Cached file changed; preserve and inspect: {relative}")
            logging.info("Verified local cache %s", relative)
        else:
            logging.info("Downloading %s", relative)
            fetch(url, target)
            checksum = sha256(target)
        item = {"relative_path": relative, "url": url, "kind": kind, "bytes": target.stat().st_size, "sha256": checksum, "downloaded_at": old.get(relative, {}).get("downloaded_at", utc_now())}
        if kind == "trip":
            metadata = pq.read_metadata(target)
            if metadata.num_rows == 0:
                raise ValueError(f"Empty month: {relative}")
            item.update(rows=metadata.num_rows, row_groups=metadata.num_row_groups, fields=metadata.schema.names, schema=str(metadata.schema))
        elif kind == "lookup":
            with target.open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                fields = reader.fieldnames
                rows = list(reader)
            if not rows or not {"LocationID", "Borough", "Zone", "service_zone"}.issubset(fields or []):
                raise ValueError("Zone lookup is empty or lacks required fields")
            item.update(rows=len(rows), fields=fields, schema={name: "CSV text; LocationID converted to integer" if name == "LocationID" else "CSV text" for name in fields})
        elif kind == "boundary":
            with zipfile.ZipFile(target) as archive:
                shp_name = next(name for name in archive.namelist() if name.lower().endswith(".shp"))
                stem = shp_name[:-4]
                with shapefile.Reader(shp=io.BytesIO(archive.read(shp_name)),
                                      shx=io.BytesIO(archive.read(stem + ".shx")),
                                      dbf=io.BytesIO(archive.read(stem + ".dbf"))) as reader:
                    fields = [list(field) for field in reader.fields if field[0] != "DeletionFlag"]
                    if reader.numRecords == 0 or "LocationID" not in [field[0] for field in fields]:
                        raise ValueError("Boundary has no features or zone key")
                    item.update(rows=reader.numRecords, row_unit="source shapefile feature records before dissolve",
                                fields=[field[0] for field in fields], schema=fields,
                                shape_type=reader.shapeType, archive_members=archive.namelist())
        elif kind == "weather":
            payload = read_json(target)
            if len(payload.get("daily", {}).get("time", [])) != 365:
                raise ValueError("Weather response must contain all 365 dates")
            item.update(rows=365, fields=list(payload["daily"]), schema=payload.get("daily_units", {}), note="ERA5 daily reanalysis; descriptive only, never a forecast feature")
        files.append(item)
        write_json(manifest_path, {"publisher": "NYC TLC / Open-Meteo", "year": 2025, "identity_note": "SHA256 is computed locally; TLC does not publish an expected SHA256. Successful Parquet metadata and full scans also validate readability.", "files": files, "complete": len(files) == len(entries), "verified_at": utc_now()})
        logging.info("Ready %s %.1f MB rows=%s", relative, item["bytes"] / 1e6, item.get("rows"))
    return manifest_path

if __name__ == "__main__":
    from .utils import configure_logging
    configure_logging("download")
    download()
