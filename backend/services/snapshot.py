"""Landing-page snapshot: live AQI for a few North Indian cities + regional fire count."""

import threading
from concurrent.futures import ThreadPoolExecutor

from cachetools import TTLCache, cached

from services.air import UpstreamError, get_air
from services.smoke_trail import _fetch_fires

# (display name, region, lat, lon) — coordinates from the Open-Meteo geocoding API.
CITIES = [
    ("New Delhi", "Delhi", 28.6214, 77.2148),
    ("Ludhiana", "Punjab", 30.912, 75.8538),
    ("Chandigarh", "Chandigarh", 30.7363, 76.7884),
    ("Lucknow", "Uttar Pradesh", 26.8393, 80.9231),
    ("Jaipur", "Rajasthan", 26.9196, 75.7878),
    ("Amritsar", "Punjab", 31.6223, 74.8753),
    ("Kanpur", "Uttar Pradesh", 26.4652, 80.3498),
    ("Patna", "Bihar", 25.5941, 85.1356),
]

# Punjab + Haryana, the main stubble-burning region (W, S, E, N).
PUNJAB_HARYANA = (73.8, 28.4, 77.6, 32.5)

_snapshot_cache = TTLCache(maxsize=1, ttl=900)


def _city(entry):
    name, region, lat, lon = entry
    try:
        current = get_air(lat, lon)["current"]
    except UpstreamError:
        return None
    return {"name": name, "region": region, "lat": lat, "lon": lon,
            "aqi": current["aqi"], "category": current["category"]}


def count_fires(fires, box=PUNJAB_HARYANA):
    west, south, east, north = box
    return sum(1 for f in fires if west <= f["lon"] <= east and south <= f["lat"] <= north)


@cached(_snapshot_cache, condition=threading.Condition())
def get_snapshot():
    with ThreadPoolExecutor(max_workers=len(CITIES)) as pool:
        cities = [c for c in pool.map(_city, CITIES) if c]
    try:
        fires = count_fires(_fetch_fires())
    except UpstreamError:
        fires = None
    if not cities and fires is None:
        raise UpstreamError("No live data available for the snapshot")
    return {"cities": cities, "fires_48h_punjab_haryana": fires}
