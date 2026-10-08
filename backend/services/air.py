"""Current air quality and 48 h forecast from Open-Meteo (no API key needed)."""

import threading
from datetime import datetime, timedelta, timezone

import requests
from cachetools import TTLCache, cached

from services.advisory import advice, category, cpcb_aqi

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

FORECAST_HOURS = 48
# "Best / worst hour to be outside" only considers waking hours.
DAYTIME = range(6, 22)

_air_cache = TTLCache(maxsize=500, ttl=1800)
_geo_cache = TTLCache(maxsize=500, ttl=86400)


def _utcnow():
    """Current UTC time (a function so tests can pin the clock)."""
    return datetime.now(timezone.utc)


class UpstreamError(Exception):
    """A data provider failed or returned something unusable."""


# condition= makes the cache thread-safe and lets parallel callers for the same
# key wait for one request instead of each fetching it.
@cached(_air_cache, condition=threading.Condition())
def _fetch_air(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "pm2_5,pm10",
        "hourly": "pm2_5,pm10",
        "timezone": "auto",
        "past_days": 1,
        "forecast_days": 3,
    }
    try:
        res = requests.get(AIR_URL, params=params, timeout=10)
        res.raise_for_status()
        return res.json()
    except requests.RequestException as exc:
        raise UpstreamError(f"Open-Meteo air quality request failed: {exc}") from exc


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def _series(raw):
    """(times, pm25, pm10) lists from a raw response; raises on a bad shape."""
    hourly = raw["hourly"]
    times, pm25, pm10 = hourly["time"], hourly["pm2_5"], hourly["pm10"]
    if not all(isinstance(x, list) for x in (times, pm25, pm10)) or not (len(times) == len(pm25) == len(pm10)):
        raise TypeError("hourly arrays missing or mismatched")
    return times, pm25, pm10


def _hourly(times, pm25, pm10):
    hours = []
    for t, p25, p10 in zip(times, pm25, pm10):
        hour_aqi, _ = cpcb_aqi(p25, p10)
        if hour_aqi is None:
            continue
        hours.append({"time": t, "pm25": p25, "pm10": p10,
                      "aqi": hour_aqi, "category": category(hour_aqi)})
    return hours


def build_air_report(raw):
    """Turn a raw Open-Meteo response into the /api/air payload."""
    try:
        times, pm25, pm10 = _series(raw)
        now_hour = raw["current"]["time"][:13] + ":00"
        now_idx = times.index(now_hour)
    except (KeyError, ValueError, TypeError) as exc:
        raise UpstreamError(f"Unexpected air quality response: {exc}") from exc

    # CPCB AQI uses 24-hour averages for particulate matter.
    window = slice(max(0, now_idx - 23), now_idx + 1)
    pm25_24h, pm10_24h = _mean(pm25[window]), _mean(pm10[window])
    aqi, dominant = cpcb_aqi(pm25_24h, pm10_24h)
    if aqi is None:
        raise UpstreamError("No PM2.5 or PM10 data for this location")

    # Forecast uses each hour's own concentration so planners can see peaks.
    forecast = _hourly(times[now_idx:now_idx + FORECAST_HOURS],
                       pm25[now_idx:now_idx + FORECAST_HOURS],
                       pm10[now_idx:now_idx + FORECAST_HOURS])

    # Filter by time, not by count: hours with no data are dropped from the forecast.
    horizon = datetime.fromisoformat(now_hour) + timedelta(hours=24)
    next_day = [f for f in forecast
                if datetime.fromisoformat(f["time"]) < horizon
                and datetime.fromisoformat(f["time"]).hour in DAYTIME]
    best = min(next_day, key=lambda f: f["aqi"], default=None)
    worst = max(next_day, key=lambda f: f["aqi"], default=None)

    return {
        "location": {
            "lat": raw.get("latitude"),
            "lon": raw.get("longitude"),
            "timezone": raw.get("timezone"),
        },
        "current": {
            "time": raw["current"]["time"],
            "aqi": aqi,
            "category": category(aqi),
            "dominant": dominant,
            "pm25": round(pm25_24h, 1) if pm25_24h is not None else None,
            "pm10": round(pm10_24h, 1) if pm10_24h is not None else None,
            "pm25_now": raw["current"].get("pm2_5"),
            "pm10_now": raw["current"].get("pm10"),
            "advice": advice(aqi),
            "basis": "24-hour average (CPCB method)",
            "source": "Open-Meteo (CAMS model)",
        },
        "forecast": forecast,
        "best_hour": best,
        "worst_hour": worst,
    }


def get_school_hours(lat, lon):
    """All hourly AQI values (yesterday → +3 days) plus today's local date.

    School Mode needs today's earlier slots too, which the forecast skips.
    """
    raw = _fetch_air(round(lat, 2), round(lon, 2))
    try:
        times, pm25, pm10 = _series(raw)
        offset = int(raw.get("utc_offset_seconds") or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise UpstreamError(f"Unexpected air quality response: {exc}") from exc
    # The real local date, not the cached response's (which can be up to 30 min
    # old — just after midnight that would make yesterday "today").
    today = (_utcnow() + timedelta(seconds=offset)).date().isoformat()
    return _hourly(times, pm25, pm10), today


def get_air(lat, lon):
    # Round so nearby requests share a cache entry (~1 km).
    return build_air_report(_fetch_air(round(lat, 2), round(lon, 2)))


@cached(_geo_cache, condition=threading.Condition())
def search_places(query):
    params = {"name": query, "count": 6, "countryCode": "IN", "language": "en"}
    try:
        res = requests.get(GEOCODE_URL, params=params, timeout=10)
        res.raise_for_status()
        return [
            {"name": r["name"], "region": r.get("admin1"), "lat": r["latitude"], "lon": r["longitude"]}
            for r in res.json().get("results") or []
        ]
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise UpstreamError(f"Geocoding request failed: {exc}") from exc
