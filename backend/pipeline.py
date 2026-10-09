"""Scheduled pipeline: an AWS Lambda run every hour by EventBridge Scheduler.

For each landing-page city it:
  1. refreshes the city's wind grids in S3 when they're over 3 h old (both
     weather models), so API instances never need to call Open-Meteo for them,
  2. computes the air report, Smoke Trail and Incoming Smoke Alert,
  3. writes them to latest/results/<city>.json and history/<date>/<hour>/<city>.json.
It also keeps an hourly copy of the NASA fire detections in history/.

The history is the record we can check forecasts against later.
"""

import logging
import re
import time
from datetime import datetime, timezone

from services import air, smoke_trail, store
from services.air import get_air
from services.smoke_trail import (
    SECOND_MODEL, download_wind, get_smoke_forecast, get_smoke_trail, save_wind, wind_store_key,
)
from services.snapshot import CITIES

log = logging.getLogger("pipeline")
log.setLevel(logging.INFO)

REFRESH_AFTER_S = 3 * 3600
# Each grid is 49 points, and Open-Meteo counts each point; pausing keeps us
# well under its per-minute limit.
PAUSE_S = 8


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _wind_age_s(center, model, now):
    saved = store.get_json(wind_store_key(*center, model))
    try:
        return (now - datetime.fromisoformat(saved["fetched_at"])).total_seconds()
    except (TypeError, KeyError, ValueError):
        return float("inf")


def run(now=None, pause_s=None):
    now = now or datetime.now(timezone.utc)
    pause_s = PAUSE_S if pause_s is None else pause_s
    # A warm Lambda keeps module caches between runs; start from fresh data.
    for cache in (smoke_trail._wind_cache, smoke_trail._fire_cache, air._air_cache):
        cache.clear()

    hour = now.strftime("history/%Y-%m-%d/%H")
    report = {"started_at": now.isoformat(), "wind_downloads": 0, "cities": [], "errors": []}

    try:
        fires = smoke_trail._fetch_fires()
        store.put_json(f"{hour}/fires.json", [
            {"lat": f["lat"], "lon": f["lon"], "frp": f["frp"], "time": f["time"].isoformat()} for f in fires
        ])
    except Exception as exc:
        report["errors"].append(f"fires: {exc}")

    for name, region, lat, lon in CITIES:
        center = (float(round(lat)), float(round(lon)))
        for model in (None, SECOND_MODEL):
            if _wind_age_s(center, model, now) < REFRESH_AFTER_S:
                continue
            try:
                save_wind(*center, model, download_wind(*center, model))
                report["wind_downloads"] += 1
            except Exception as exc:
                report["errors"].append(f"{name} wind {model or 'best'}: {exc}")
            time.sleep(pause_s)

        result = {"city": name, "region": region, "lat": lat, "lon": lon, "generated_at": now.isoformat()}
        for key, compute in (("air", get_air), ("smoke_trail", get_smoke_trail),
                             ("smoke_forecast", get_smoke_forecast)):
            try:
                result[key] = compute(lat, lon)
            except Exception as exc:
                result[key] = None
                report["errors"].append(f"{name} {key}: {exc}")
        store.put_json(f"latest/results/{slug(name)}.json", result)
        store.put_json(f"{hour}/{slug(name)}.json", result)
        if result["air"] or result["smoke_forecast"]:
            report["cities"].append(name)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    store.put_json("latest/run.json", report)
    return report


def handler(event, context):
    report = run()
    log.info("Pipeline: %d cities, %d wind downloads, %d errors",
             len(report["cities"]), report["wind_downloads"], len(report["errors"]))
    for err in report["errors"]:
        log.warning(err)
    if not report["cities"]:
        # Fail the invocation so the CloudWatch alarm fires.
        raise RuntimeError("Pipeline produced no results: " + "; ".join(report["errors"][:5]))
    return {"cities": len(report["cities"]), "errors": len(report["errors"])}
