"""Pack or restore the two large offline Power BI tables with SHA256 checks.

Uses only Python's standard library; restoration does not download TLC data.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
TABLES = ("fact_zone_hour.csv", "simulation_hourly.csv")
ARCHIVE = ROOT / "reports/tables/powerbi_large_tables.zip"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def matches(path, identity):
    return path.is_file() and path.stat().st_size == identity["bytes"] and digest(path) == identity["sha256"]


def pack():
    folder = ROOT / "reports/tables"
    identities = {name: {"bytes": (folder / name).stat().st_size, "sha256": digest(folder / name)} for name in TABLES}
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name in TABLES:
            info = ZipInfo(name, date_time=(2025, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            with (folder / name).open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
        info = ZipInfo("manifest.json", date_time=(2025, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, json.dumps(identities, indent=2).encode("utf-8"))
    print(f"Packed {len(TABLES)} tables: {ARCHIVE.stat().st_size:,} bytes")


def restore(destination):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARCHIVE) as archive:
        if sorted(archive.namelist()) != sorted((*TABLES, "manifest.json")):
            raise ValueError("Unexpected archive members")
        identities = json.loads(archive.read("manifest.json"))
        if set(identities) != set(TABLES):
            raise ValueError("Unexpected table manifest")
        for name in TABLES:
            target = destination / name
            identity = identities[name]
            if matches(target, identity):
                print(f"Verified cached table: {name}")
                continue
            with tempfile.NamedTemporaryFile(dir=destination, prefix=name + ".", suffix=".part", delete=False) as temporary:
                temp_path = Path(temporary.name)
                try:
                    with archive.open(name) as source:
                        shutil.copyfileobj(source, temporary, length=1024 * 1024)
                except BaseException:
                    temporary.close()
                    temp_path.unlink(missing_ok=True)
                    raise
            try:
                if not matches(temp_path, identity):
                    raise ValueError(f"Size or SHA256 mismatch: {name}")
                temp_path.replace(target)
            finally:
                temp_path.unlink(missing_ok=True)
            print(f"Restored and verified table: {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", action="store_true")
    parser.add_argument("--destination", type=Path, default=ROOT / "reports/tables")
    args = parser.parse_args()
    if args.pack:
        pack()
    else:
        restore(args.destination)
