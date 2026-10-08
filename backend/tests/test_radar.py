from datetime import timedelta

import pytest

from services import radar
from services.air import UpstreamError
from tests.test_smoke_trail import NOW, constant_grid


def test_wind_components_point_where_the_air_goes():
    # FROM the north at 10 km/h → air moves south: east 0, north -10
    assert radar.wind_components(10, 0) == (-0.0, -10.0)
    # FROM the west → air moves east
    e, n = radar.wind_components(10, 270)
    assert e == pytest.approx(10) and n == pytest.approx(0, abs=1e-9)
    assert radar.wind_components(None, 90) == (None, None)


def test_build_radar_frames_fires_and_cities():
    grid = constant_grid(10, 270, hours=48, future=48)
    fires = [
        {"lat": 30.2, "lon": 75.8, "frp": 5.0, "time": NOW - timedelta(hours=30)},  # 6 h before first frame
        {"lat": 30.2, "lon": 75.8, "frp": 5.0, "time": NOW - timedelta(hours=70)},  # too old
        {"lat": 10.0, "lon": 75.8, "frp": 5.0, "time": NOW},                        # outside grid
    ]
    cities = [{"name": "Delhi", "lat": 28.6, "lon": 77.2, "aqi": [1]}, {"name": "Far", "lat": 10.0, "lon": 77.0, "aqi": [1]}]
    r = radar.build_radar(grid, fires, cities, NOW)
    assert len(r["frames"]) == 49 and r["now_index"] == 24
    n_points = len(r["grid"]["lats"]) * len(r["grid"]["lons"])
    assert len(r["u"]) == 49 and len(r["u"][0]) == n_points
    assert r["u"][0][0] == pytest.approx(10)          # westerly wind → moving east
    assert [f["t"] for f in r["fires"]] == [-6.0]
    assert [c["name"] for c in r["cities"]] == ["Delhi"]


def test_build_radar_needs_wind():
    grid = constant_grid(10, 270, hours=0)
    with pytest.raises(UpstreamError):
        radar.build_radar(grid, [], [], NOW + timedelta(days=10))


def test_city_series_aligns_local_times_to_utc_frames(monkeypatch):
    raw = {
        "utc_offset_seconds": 19800,  # IST, UTC+5:30
        "hourly": {"time": ["2026-10-09T17:00", "2026-10-09T18:00"], "pm2_5": [100, 30], "pm10": [None, None]},
    }
    monkeypatch.setattr(radar, "_fetch_air", lambda lat, lon: raw)
    frames = ["2026-10-09T11:00", "2026-10-09T12:00", "2026-10-09T13:00"]
    series = radar._city_series(("Delhi", "Delhi", 28.6, 77.2), frames)
    # 17:00 IST = 11:30 UTC → the 11:00 frame (half-hour offsets round down)
    assert series["aqi"] == [232, 50, None]  # PM2.5 30 = top of "Good" → AQI 50


def test_city_without_data_is_dropped(monkeypatch):
    def boom(lat, lon):
        raise UpstreamError("down")
    monkeypatch.setattr(radar, "_fetch_air", boom)
    assert radar._city_series(("X", "Y", 1, 2), ["2026-10-09T11:00"]) is None
