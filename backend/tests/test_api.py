from datetime import datetime, timezone
import pytest

import app as app_module
from services import air


def make_raw(now="2026-10-09T10:15", pm25=100.0, pm10=200.0, hours=96):
    """Fake Open-Meteo response: flat concentrations from 2026-10-08 00:00."""
    times = [f"2026-10-{8 + h // 24:02d}T{h % 24:02d}:00" for h in range(hours)]
    return {
        "latitude": 28.6, "longitude": 77.2, "timezone": "Asia/Kolkata",
        "current": {"time": now, "pm2_5": pm25, "pm10": pm10},
        "hourly": {"time": times, "pm2_5": [pm25] * hours, "pm10": [pm10] * hours},
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(air, "_fetch_air", lambda lat, lon: make_raw())
    monkeypatch.setattr(air, "_utcnow", lambda: datetime(2026, 10, 9, 10, 15, tzinfo=timezone.utc))
    return app_module.app.test_client()


def test_build_air_report_shapes_forecast():
    report = air.build_air_report(make_raw())
    # PM2.5 100 → 201 + 99·9/29 ≈ 232 beats PM10 200 → ~167
    assert report["current"]["aqi"] == 232
    assert report["current"]["category"] == "Poor"
    assert report["current"]["dominant"] == "pm25"
    assert report["forecast"][0]["time"] == "2026-10-09T10:00"
    assert len(report["forecast"]) == air.FORECAST_HOURS


def test_best_and_worst_hours_ignore_night():
    raw = make_raw()
    times = raw["hourly"]["time"]
    raw["hourly"]["pm2_5"][times.index("2026-10-10T03:00")] = 5     # night: ignored
    raw["hourly"]["pm2_5"][times.index("2026-10-09T15:00")] = 40    # daytime best
    report = air.build_air_report(raw)
    assert report["best_hour"]["time"] == "2026-10-09T15:00"


def test_bad_upstream_shape_raises():
    with pytest.raises(air.UpstreamError):
        air.build_air_report({"hourly": {}})


def test_air_endpoint(client):
    res = client.get("/api/air?lat=28.61&lon=77.21")
    assert res.status_code == 200
    assert res.get_json()["current"]["aqi"] == 232


def test_school_endpoint_covers_today_and_tomorrow(client):
    res = client.get("/api/school?lat=28.61&lon=77.21")
    days = res.get_json()["days"]
    assert [d["date"] for d in days] == ["2026-10-09", "2026-10-10"]
    # 08:00 today is before "now" (10:15) but must still be evaluated.
    assert days[0]["slots"][0]["decision"] == "limit"


def test_school_slot_times_can_be_customised(client):
    res = client.get("/api/school?lat=28.6&lon=77.2&assembly=07:45&pe=12:00")
    slots = res.get_json()["days"][0]["slots"]
    # Rounded down to the hour; dismissal keeps its default.
    assert [s["time"] for s in slots] == ["07:00", "12:00", "14:00"]


@pytest.mark.parametrize("bad", ["8am", "24:00", "7:5", "12:60"])
def test_bad_slot_time_is_rejected(client, bad):
    assert client.get(f"/api/school?lat=28.6&lon=77.2&pe={bad}").status_code == 400


@pytest.mark.parametrize("query", ["", "?lat=28.6", "?lat=abc&lon=77", "?lat=95&lon=77"])
def test_bad_coordinates_are_rejected(client, query):
    assert client.get(f"/api/air{query}").status_code == 400


def test_upstream_failure_returns_502(monkeypatch):
    def boom(lat, lon):
        raise air.UpstreamError("down")
    monkeypatch.setattr(air, "_fetch_air", boom)
    res = app_module.app.test_client().get("/api/air?lat=28.6&lon=77.2")
    assert res.status_code == 502
