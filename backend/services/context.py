"""Compact snapshot of a city's live data, given to the assistant as its only facts."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.advisory import in_delhi_ncr, school_plan
from services import replay
from services.air import get_air, get_school_hours
from services.smoke_trail import get_smoke_forecast, get_smoke_trail


def _local_now(timezone_name):
    try:
        return datetime.now(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def city_context(lat, lon, place_name, slots, replay_date=None):
    if replay_date:
        # Demo replay: the same facts, from the captured snapshot.
        air = replay.api(replay_date, "air", lat, lon)
        hours, today = replay.school_hours(replay_date, lat, lon)
        trail_fetch = lambda: replay.api(replay_date, "smoke-trail", lat, lon)  # noqa: E731
        forecast_fetch = lambda: replay.api(replay_date, "smoke-forecast", lat, lon)  # noqa: E731
    else:
        air = get_air(lat, lon)
        hours, today = get_school_hours(lat, lon)
        trail_fetch = lambda: get_smoke_trail(lat, lon)  # noqa: E731
        forecast_fetch = lambda: get_smoke_forecast(lat, lon)  # noqa: E731
    current = air["current"]

    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    school = [
        {
            "date": day["date"],
            "grap_stage": day["grap_stage"],
            "slots": [
                {"activity": s["label"], "time": s["time"], "aqi": s["aqi"],
                 "decision": s["verdict"], "advice": s["advice"]}
                for s in day["slots"]
            ],
        }
        for day in school_plan(hours, [today, tomorrow], slots)
    ]

    # Smoke data is a bonus: fetch both in parallel, and answer without them if
    # either fails for any reason.
    with ThreadPoolExecutor(max_workers=2) as pool:
        trail_job = pool.submit(trail_fetch)
        forecast_job = pool.submit(forecast_fetch)

    try:
        trail = trail_job.result()["summary"]
        smoke = {
            "hours_traced": trail["hours_traced"],
            "distance_km": trail["trail_km"],
            "air_stagnant": trail["stagnant"],
            "fires_on_path": trail["fire_count"],
            "top_districts": [
                {"district": d["district"], "state": d["state"], "fires": d["fires"]}
                for d in trail["top_districts"]
            ],
            "fires_outside_named_districts": trail["other_fires"],
        }
    except Exception:  # optional data: never let it break the answer
        smoke = "unavailable right now"

    try:
        alert = forecast_job.result()["alert"]
        incoming = {
            "smoke_likely_arriving": alert["incoming"],
            "first_arrival_utc": alert["first_arrival_time"],
            "hours_from_now": alert["first_arrival_h"],
            "from_fires": alert["fires"],
            "source_districts": alert["districts"],
            "note": "Forward trajectories from current fires on forecast winds; likely, not certain.",
        }
    except Exception:  # optional data: never let it break the answer
        incoming = "unavailable right now"

    def brief(hour):
        return hour and {"time": hour["time"], "aqi": hour["aqi"]}

    local_time = _local_now(air["location"]["timezone"])
    if replay_date:
        captured = datetime.fromisoformat(replay.marker(replay_date)["captured_at_utc"])
        try:
            local_time = captured.astimezone(ZoneInfo(air["location"]["timezone"])).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    return {
        "data_mode": f"DEMO REPLAY of data captured {replay_date}" if replay_date else "latest",
        "city": place_name,
        "grap_applies_here": in_delhi_ncr(lat, lon),
        "local_time": local_time,
        "air_now": {
            "aqi": current["aqi"],
            "category": current["category"],
            "main_pollutant": {"pm25": "PM2.5", "pm10": "PM10"}.get(current["dominant"], current["dominant"]),
            "pm25_24h_avg": current["pm25"],
            "pm10_24h_avg": current["pm10"],
            "pm25_this_hour": current["pm25_now"],
            "advice": current["advice"],
            "note": "AQI is a 24-hour average (CPCB method); forecast values are hourly.",
        },
        # Same 48 h the dashboard chart shows, so answers match what users see.
        "forecast_next_48h": [
            {"time": f["time"], "aqi": f["aqi"], "pm25": f["pm25"]}
            for f in air["forecast"]
        ],
        "best_daytime_hour_next_24h": brief(air["best_hour"]),
        "worst_daytime_hour_next_24h": brief(air["worst_hour"]),
        "school_mode": school,
        "smoke_trail": smoke,
        "incoming_smoke_next_48h": incoming,
    }
