"""Demo replay: serve a dated snapshot of real data captured earlier.

Snapshots live in data/replay/<date>/ (see scripts/capture_snapshot.py). Every
replay response carries a "_replay" marker so the UI can label it — replay data
is never presented as live.
"""

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from services.air import _hourly, _series
from services.errors import BadRequest

ROOT = Path(__file__).resolve().parent.parent / "data" / "replay"
MATCH_DEG = 0.3  # a request within this distance of a snapshot city uses its data


class ReplayNotFound(Exception):
    """No replay data for this place (→ HTTP 404)."""


@lru_cache(maxsize=4)
def _manifest(date):
    path = ROOT / date / "manifest.json"
    if not date or "/" in date or ".." in date or not path.is_file():
        raise BadRequest(f"No demo replay available for {date!r}")
    return json.loads(path.read_text())


def available():
    return sorted(p.name for p in ROOT.iterdir() if (p / "manifest.json").is_file()) if ROOT.is_dir() else []


def marker(date):
    m = _manifest(date)
    return {"date": date, "captured_at_utc": m["captured_at_utc"], "live": False}


def city_key(date, lat, lon):
    for key, c in _manifest(date)["cities"].items():
        if abs(c["lat"] - lat) <= MATCH_DEG and abs(c["lon"] - lon) <= MATCH_DEG:
            return key
    names = ", ".join(c["name"] for c in _manifest(date)["cities"].values())
    raise ReplayNotFound(f"The {date} demo replay only covers {names}.")


@lru_cache(maxsize=64)
def _load(date, name):
    return json.loads((ROOT / date / name).read_text())


def api(date, endpoint, lat, lon):
    """A stored API response, plus the replay marker."""
    key = city_key(date, lat, lon)
    data = dict(_load(date, f"api/{key}.{endpoint}.json"))
    data["_replay"] = marker(date)
    return data


def school_hours(date, lat, lon):
    """(hours, today) recomputed from the captured raw air data, so custom
    school times work in replay exactly as they do live."""
    key = city_key(date, lat, lon)
    city = _manifest(date)["cities"][key]
    for entry in _manifest(date)["raw"]:
        params = entry.get("params") or {}
        if "air-quality" in entry["url"] and params.get("latitude") == round(city["lat"], 2) \
                and params.get("longitude") == round(city["lon"], 2):
            raw = json.loads((ROOT / date / entry["file"]).read_text())
            break
    else:
        raise ReplayNotFound(f"No captured air data for {city['name']}.")
    captured = datetime.fromisoformat(_manifest(date)["captured_at_utc"])
    today = (captured + timedelta(seconds=int(raw.get("utc_offset_seconds") or 0))).date().isoformat()
    return _hourly(*_series(raw)), today
