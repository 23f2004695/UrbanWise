"""Smoke Radar: everything the time-lapse map needs for -24 h … +24 h.

Wind is returned as east/north components (km/h) per grid point per hour, so the
browser can animate particles. Times are UTC throughout.
"""

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from services.air import UpstreamError, _fetch_air, _hourly, _series
from services.smoke_trail import _fetch_fires, _fetch_wind_grid
from services.snapshot import CITIES

PAST_H = 24
FUTURE_H = 24
FIRE_LOOKBACK_H = 36  # fires seen up to 36 h before the first frame still emit smoke


def wind_components(speed, direction):
    """Meteorological (speed, from-direction) → (east, north) the air moves towards."""
    if speed is None or direction is None:
        return None, None
    rad = math.radians(direction)
    return round(-speed * math.sin(rad), 2), round(-speed * math.cos(rad), 2)


def _utc_hour(local_iso, offset_seconds):
    # India is UTC+5:30, so local hours land on :30 in UTC; callers format with
    # %H:00, which rounds down to the frame (fine for a time-lapse).
    t = datetime.fromisoformat(local_iso).replace(tzinfo=timezone.utc)
    return t - timedelta(seconds=offset_seconds)


def _city_series(entry, frames):
    """Hourly AQI for one city, aligned to the radar frames (UTC)."""
    name, region, lat, lon = entry
    try:
        raw = _fetch_air(round(lat, 2), round(lon, 2))
        hours = _hourly(*_series(raw))
        offset = raw.get("utc_offset_seconds", 0)
    except (UpstreamError, KeyError, TypeError, ValueError):
        return None
    by_utc = {_utc_hour(h["time"], offset).strftime("%Y-%m-%dT%H:00"): h for h in hours}
    aqi = [by_utc.get(f, {}).get("aqi") for f in frames]
    if not any(a is not None for a in aqi):
        return None
    return {"name": name, "region": region, "lat": lat, "lon": lon, "aqi": aqi}


def build_radar(grid, fires, cities, now):
    """Pure assembly of the radar payload (no network)."""
    start = now - timedelta(hours=PAST_H)
    frames = [(start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(PAST_H + FUTURE_H + 1)]
    available = [f for f in frames if f in grid.time_index]
    if len(available) < 2:
        raise UpstreamError("Not enough wind data for the radar")

    u, v = [], []
    for f in available:
        k = grid.time_index[f]
        fu, fv = [], []
        for i in range(len(grid.lats)):
            for j in range(len(grid.lons)):
                speeds, dirs = grid.samples[(i, j)]
                e, n = wind_components(speeds[k], dirs[k])
                fu.append(e)
                fv.append(n)
        u.append(fu)
        v.append(fv)

    first = datetime.fromisoformat(available[0]).replace(tzinfo=timezone.utc)
    lat_min, lat_max = grid.lats[0], grid.lats[-1]
    lon_min, lon_max = grid.lons[0], grid.lons[-1]
    radar_fires = [
        {"lat": f["lat"], "lon": f["lon"], "frp": f["frp"],
         # hours relative to the first frame (negative = before the time-lapse starts)
         "t": round((f["time"] - first).total_seconds() / 3600, 2)}
        for f in fires
        if lat_min <= f["lat"] <= lat_max and lon_min <= f["lon"] <= lon_max
        and (f["time"] - first).total_seconds() / 3600 >= -FIRE_LOOKBACK_H
    ]

    return {
        "frames": available,
        "now_index": available.index(now.strftime("%Y-%m-%dT%H:00")) if now.strftime("%Y-%m-%dT%H:00") in available else None,
        "grid": {"lats": grid.lats, "lons": grid.lons},  # u/v are row-major: lat index, then lon
        "u": u,
        "v": v,
        "fires": radar_fires,
        "cities": [c for c in cities if lat_min <= c["lat"] <= lat_max and lon_min <= c["lon"] <= lon_max],
    }


def get_radar(lat, lon, now=None):
    now = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    grid = _fetch_wind_grid(float(round(lat)), float(round(lon)))
    start = now - timedelta(hours=PAST_H)
    frames = [(start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(PAST_H + FUTURE_H + 1)]
    with ThreadPoolExecutor(max_workers=len(CITIES)) as pool:
        cities = [c for c in pool.map(lambda e: _city_series(e, frames), CITIES) if c]
    return build_radar(grid, _fetch_fires(), cities, now)
