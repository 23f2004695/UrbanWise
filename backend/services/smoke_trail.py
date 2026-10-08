"""Smoke Trail: where did the air over a city come from, and which fires did it pass?

Simplified back-trajectory: start at the city now, step backwards one hour at a
time against the ~750 m (925 hPa) wind, then match satellite fire detections
along that path. Results are "likely contributing sources", not exact shares.
"""

import csv
import io
import json
import math
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cachetools import TTLCache, cached

from services.air import UpstreamError

WIND_URL = "https://api.open-meteo.com/v1/forecast"
# NASA FIRMS public 48 h file for South Asia (VIIRS on Suomi NPP). No key needed.
FIRES_URL = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_48h.csv"
)

HOURS = 48
GRID_HALF_SPAN = 6.0   # degrees either side of the city
GRID_STEP = 2.0        # degrees between wind sample points (7 × 7 grid; denser grids take ~10 s)
KM_PER_DEG_LAT = 111.0
STAGNANT_KM = 50       # whole trail within this distance → air barely moved
SATELLITE_WINDOW_H = 12  # VIIRS passes ~twice a day; a detection represents ±12 h
DISTRICT_MAX_KM = 60     # beyond this a fire is not labelled with a district

_wind_cache = TTLCache(maxsize=200, ttl=3600)
_fire_cache = TTLCache(maxsize=1, ttl=1800)

_DISTRICTS = json.loads(
    (Path(__file__).resolve().parent.parent / "data" / "districts.json").read_text()
)


# ---------- geometry ----------

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def corridor_km(hours_ago):
    """How far from the trail a fire may be; uncertainty grows going back."""
    return min(15 + 1.5 * hours_ago, 75)


# ---------- wind ----------

class WindGrid:
    """Hourly wind samples on a regular lat/lon grid.

    samples[(i, j)] = (speeds_kmh, directions_deg) indexed like `times`.
    Directions are meteorological: where the wind blows FROM.
    """

    def __init__(self, lats, lons, times, samples):
        self.lats, self.lons = lats, lons
        self.time_index = {t: k for k, t in enumerate(times)}
        self.samples = samples

    def contains(self, lat, lon):
        half = GRID_STEP / 2
        return (self.lats[0] - half <= lat <= self.lats[-1] + half
                and self.lons[0] - half <= lon <= self.lons[-1] + half)

    def at(self, lat, lon, when):
        """Nearest grid point's wind at hour `when` (UTC datetime), or None."""
        k = self.time_index.get(when.strftime("%Y-%m-%dT%H:00"))
        if k is None:
            return None
        i = min(range(len(self.lats)), key=lambda n: abs(self.lats[n] - lat))
        j = min(range(len(self.lons)), key=lambda n: abs(self.lons[n] - lon))
        speeds, dirs = self.samples[(i, j)]
        if speeds[k] is None or dirs[k] is None:
            return None
        return speeds[k], dirs[k]


def _grid_axis(center):
    n = int(GRID_HALF_SPAN * 2 / GRID_STEP) + 1
    start = center - GRID_HALF_SPAN
    return [round(start + GRID_STEP * k, 2) for k in range(n)]


def _get_json_with_retry(url, params, label, attempts=2):
    """GET JSON, retrying once on timeouts and 5xx (Open-Meteo returns 503 under load)."""
    for attempt in range(attempts):
        try:
            # Short enough that a retry still fits AWS API Gateway's 29 s limit.
            res = requests.get(url, params=params, timeout=10)
            if res.status_code < 500 or attempt == attempts - 1:
                res.raise_for_status()
                return res.json()
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == attempts - 1:
                raise UpstreamError(f"{label} request failed: {exc}") from exc
        except requests.RequestException as exc:
            raise UpstreamError(f"{label} request failed: {exc}") from exc
        time.sleep(1.5)
    raise UpstreamError(f"{label} request failed")


@cached(_wind_cache, condition=threading.Condition())
def _fetch_wind_grid(center_lat, center_lon):
    lats, lons = _grid_axis(center_lat), _grid_axis(center_lon)
    points = [(la, lo) for la in lats for lo in lons]
    params = {
        "latitude": ",".join(str(p[0]) for p in points),
        "longitude": ",".join(str(p[1]) for p in points),
        "hourly": "wind_speed_925hPa,wind_direction_925hPa",
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
        "past_days": 2,
        "forecast_days": 3,  # future hours for the Incoming Smoke Alert
    }
    body = _get_json_with_retry(WIND_URL, params, "Open-Meteo wind")
    if not isinstance(body, list) or len(body) != len(points):
        raise UpstreamError("Unexpected wind grid response")

    try:
        samples = {}
        for n, loc in enumerate(body):
            h = loc["hourly"]
            samples[(n // len(lons), n % len(lons))] = (
                list(h["wind_speed_925hPa"]), list(h["wind_direction_925hPa"]),
            )
        return WindGrid(lats, lons, list(body[0]["hourly"]["time"]), samples)
    except (KeyError, TypeError, IndexError) as exc:
        raise UpstreamError(f"Unexpected wind grid response: {exc}") from exc


def back_trajectory(lat, lon, grid, now, hours=HOURS):
    """Trace the air backwards. Returns [(lat, lon, hours_ago), ...]."""
    path = [(lat, lon, 0)]
    for h in range(1, hours + 1):
        wind = grid.at(lat, lon, now - timedelta(hours=h))
        if wind is None:
            break
        speed, direction = wind
        rad = math.radians(direction)
        # Wind comes FROM `direction`, so one hour earlier the air was that way.
        lat += speed * math.cos(rad) / KM_PER_DEG_LAT
        lon += speed * math.sin(rad) / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))
        if not grid.contains(lat, lon):
            break
        path.append((round(lat, 4), round(lon, 4), h))
    return path


# ---------- fires ----------

def parse_fires(text):
    fires = []
    for row in csv.DictReader(io.StringIO(text)):
        # VIIRS files use "low/nominal/high" (seen 8 Oct) or "l/n/h" in some formats.
        if (row.get("confidence") or "").strip().lower() in ("l", "low"):
            continue
        try:
            when = datetime.strptime(
                f"{row['acq_date']} {row['acq_time'].zfill(4)}", "%Y-%m-%d %H%M"
            ).replace(tzinfo=timezone.utc)
            fires.append({
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"]),
                "frp": float(row.get("frp") or 0),
                "time": when,
            })
        except (KeyError, ValueError):
            continue
    return fires


@cached(_fire_cache, condition=threading.Condition())
def _fetch_fires():
    try:
        res = requests.get(FIRES_URL, timeout=15)
        res.raise_for_status()
    except requests.RequestException as exc:
        raise UpstreamError(f"NASA FIRMS request failed: {exc}") from exc
    return parse_fires(res.text)


def fires_on_trail(path, fires, now):
    """Fires near the trail at roughly the time the air passed over them."""
    hits = []
    for f in fires:
        fire_hours_ago = (now - f["time"]).total_seconds() / 3600
        for lat, lon, h in path:
            if abs(fire_hours_ago - h) > SATELLITE_WINDOW_H:
                continue
            if haversine_km(lat, lon, f["lat"], f["lon"]) <= corridor_km(h):
                hits.append({**f, "trail_hours_ago": h})
                break
    return hits


def nearest_district(lat, lon, districts=None):
    best, best_km = None, DISTRICT_MAX_KM
    for d in districts if districts is not None else _DISTRICTS:
        km = haversine_km(lat, lon, d["lat"], d["lon"])
        if km < best_km:
            best, best_km = d, km
    return best


# ---------- summary ----------

def summarize(path, hits, districts=None):
    origin = path[0]
    max_km = max((haversine_km(origin[0], origin[1], p[0], p[1]) for p in path), default=0)
    trail_km = sum(
        haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(path, path[1:])
    )

    by_district = {}
    for f in hits:
        d = nearest_district(f["lat"], f["lon"], districts)
        f["district"] = d["district"] if d else None
        f["state"] = d["state"] if d else None
        if d:
            entry = by_district.setdefault(d["district"], {
                "district": d["district"], "state": d["state"], "fires": 0, "frp": 0.0,
            })
            entry["fires"] += 1
            entry["frp"] += f["frp"]

    top = sorted(by_district.values(), key=lambda e: (e["frp"], e["fires"]), reverse=True)
    for e in top:
        e["frp"] = round(e["frp"], 1)

    return {
        "fire_count": len(hits),
        "top_districts": top[:5],
        # Fires named in top_districts don't cover everything; say how many aren't.
        "other_fires": len(hits) - sum(e["fires"] for e in top[:5]),
        "trail_km": round(trail_km),
        "hours_traced": path[-1][2],
        "stagnant": max_km < STAGNANT_KM,
    }


def get_smoke_trail(lat, lon, now=None):
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    # Snap the grid centre to whole degrees so nearby cities share a cached grid.
    grid = _fetch_wind_grid(float(round(lat)), float(round(lon)))
    path = back_trajectory(lat, lon, grid, now)
    if len(path) < 2:
        raise UpstreamError("Not enough wind data to trace the air")

    fires = _fetch_fires()
    hits = fires_on_trail(path, fires, now)
    summary = summarize(path, hits)

    # Other fires in the trail's area are sent too, so the map can show them faded.
    lats = [p[0] for p in path]
    lons = [p[1] for p in path]
    pad = 1.0
    nearby = [
        {"lat": f["lat"], "lon": f["lon"], "frp": f["frp"]}
        for f in fires
        if min(lats) - pad <= f["lat"] <= max(lats) + pad
        and min(lons) - pad <= f["lon"] <= max(lons) + pad
    ]

    return {
        "generated_at": now.isoformat(),
        "trail": [list(p) for p in path],
        "fires": [
            {
                "lat": f["lat"], "lon": f["lon"], "frp": f["frp"],
                "hours_ago": round((now - f["time"]).total_seconds() / 3600),
                "district": f["district"], "state": f["state"],
            }
            for f in hits
        ],
        "nearby_fires": nearby,
        "summary": summary,
        "method": "Simplified 48 h back-trajectory using 925 hPa winds (Open-Meteo) "
                  "and NASA FIRMS VIIRS fire detections. Shows likely contributing sources.",
    }


# ---------- Incoming Smoke Alert: the same engine, run forwards ----------

CLUSTER_DEG = 0.5      # fires grouped into ~50 km cells
# Satellites see most fires on one daytime pass per day, and NASA publishes it
# a few hours later, so the latest big pass can be ~28 h old. 36 h always
# includes it (24 h missed it entirely when tested on 8 Oct).
CLUSTER_MAX_AGE_H = 36
MAX_CLUSTERS = 8
LOCAL_KM = 30          # fires this close are "local", not incoming


def forward_trajectory(lat, lon, grid, start, hours=HOURS):
    """Where air (and smoke) released at `start` goes. [(lat, lon, hours_ahead), ...]"""
    path = [(lat, lon, 0)]
    for h in range(1, hours + 1):
        wind = grid.at(lat, lon, start + timedelta(hours=h - 1))
        if wind is None:
            break
        speed, direction = wind
        rad = math.radians(direction)
        # Wind comes FROM `direction`, so the air moves the opposite way.
        lat -= speed * math.cos(rad) / KM_PER_DEG_LAT
        lon -= speed * math.sin(rad) / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))
        if not grid.contains(lat, lon):
            break
        path.append((round(lat, 4), round(lon, 4), h))
    return path


def fire_clusters(fires, now, max_age_h=CLUSTER_MAX_AGE_H, top=MAX_CLUSTERS):
    """Group recent fires into grid cells, strongest (by total FRP) first."""
    cells = {}
    for f in fires:
        age = (now - f["time"]).total_seconds() / 3600
        if not 0 <= age <= max_age_h:
            continue
        # floor, not round: round() sends .5 to the nearest even number, which
        # split fires 2 km apart into different cells.
        key = (math.floor(f["lat"] / CLUSTER_DEG), math.floor(f["lon"] / CLUSTER_DEG))
        c = cells.setdefault(key, {"lat": 0.0, "lon": 0.0, "fires": 0, "frp": 0.0})
        c["lat"] += f["lat"]
        c["lon"] += f["lon"]
        c["fires"] += 1
        c["frp"] += f["frp"]
    clusters = [
        {"lat": round(c["lat"] / c["fires"], 4), "lon": round(c["lon"] / c["fires"], 4),
         "fires": c["fires"], "frp": round(c["frp"], 1)}
        for c in cells.values()
    ]
    clusters.sort(key=lambda c: (c["frp"], c["fires"]), reverse=True)
    return clusters[:top]


def first_arrival(path, lat, lon):
    """(hours_ahead, closest_km) — hours_ahead is None if the smoke never reaches the city."""
    closest = min(haversine_km(lat, lon, p[0], p[1]) for p in path)
    for p_lat, p_lon, h in path[1:]:
        if haversine_km(lat, lon, p_lat, p_lon) <= corridor_km(h):
            return h, round(closest)
    return None, round(closest)


def smoke_forecast(lat, lon, grid, fires, now, districts=None):
    """Pure core of the Incoming Smoke Alert (no network)."""
    local = sum(1 for f in fires
                if (now - f["time"]).total_seconds() <= CLUSTER_MAX_AGE_H * 3600
                and haversine_km(lat, lon, f["lat"], f["lon"]) <= LOCAL_KM)
    results = []
    for c in fire_clusters(fires, now):
        if haversine_km(lat, lon, c["lat"], c["lon"]) <= LOCAL_KM or not grid.contains(c["lat"], c["lon"]):
            continue
        path = forward_trajectory(c["lat"], c["lon"], grid, now)
        if len(path) < 2:
            continue
        arrival_h, closest_km = first_arrival(path, lat, lon)
        d = nearest_district(c["lat"], c["lon"], districts)
        results.append({
            **c,
            "district": d["district"] if d else None,
            "state": d["state"] if d else None,
            "path": [list(p) for p in path],
            "arrival_h": arrival_h,
            "arrival_time": (now + timedelta(hours=arrival_h)).isoformat() if arrival_h is not None else None,
            "closest_km": closest_km,
        })

    arriving = sorted((r for r in results if r["arrival_h"] is not None), key=lambda r: r["arrival_h"])
    alert = {
        "incoming": bool(arriving),
        "first_arrival_h": arriving[0]["arrival_h"] if arriving else None,
        "first_arrival_time": arriving[0]["arrival_time"] if arriving else None,
        "fires": sum(r["fires"] for r in arriving),
        "districts": list(dict.fromkeys(r["district"] for r in arriving if r["district"])),
    }
    return {"clusters": results, "alert": alert, "local_fires": local}


def get_smoke_forecast(lat, lon, now=None):
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    grid = _fetch_wind_grid(float(round(lat)), float(round(lon)))
    result = smoke_forecast(lat, lon, grid, _fetch_fires(), now)
    return {
        "generated_at": now.isoformat(),
        **result,
        "method": "Forward trajectories from today's fire clusters using forecast winds ~750 m up "
                  "(Open-Meteo). Shows smoke that may arrive (model estimate), not a guarantee.",
    }
