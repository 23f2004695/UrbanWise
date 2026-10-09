from datetime import datetime, timedelta, timezone

import pytest

from services import smoke_trail as st

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)


def constant_grid(speed, direction, center=(28.6, 77.2), hours=72, future=0):
    """Wind grid with the same wind everywhere, covering `hours` before NOW
    and `future` hours after it."""
    lats, lons = st._grid_axis(center[0]), st._grid_axis(center[1])
    start = NOW - timedelta(hours=hours)
    times = [(start + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(hours + future + 1)]
    samples = {
        (i, j): ([speed] * len(times), [direction] * len(times))
        for i in range(len(lats)) for j in range(len(lons))
    }
    return st.WindGrid(lats, lons, times, samples)


def test_north_west_wind_traces_back_to_the_north_west():
    path = st.back_trajectory(28.6, 77.2, constant_grid(10, 315), NOW, hours=24)
    lat, lon, h = path[-1]
    assert h == 24
    assert lat > 28.6 and lon < 77.2
    # 10 km/h for 24 h ≈ 240 km from the start.
    assert st.haversine_km(28.6, 77.2, lat, lon) == pytest.approx(240, rel=0.03)


def test_north_wind_moves_trail_due_north():
    path = st.back_trajectory(28.6, 77.2, constant_grid(10, 0), NOW, hours=10)
    lat, lon, _ = path[-1]
    assert lat == pytest.approx(28.6 + 100 / 111, abs=0.01)
    assert lon == pytest.approx(77.2, abs=0.001)


def test_trail_stops_at_grid_edge():
    # 60 km/h for 48 h would be ~2900 km, far outside the ±6° grid.
    path = st.back_trajectory(28.6, 77.2, constant_grid(60, 270), NOW)
    assert path[-1][2] < 48
    assert len(path) > 1


def test_trail_stops_when_wind_data_runs_out():
    path = st.back_trajectory(28.6, 77.2, constant_grid(5, 0, hours=6), NOW)
    assert path[-1][2] == 6


def test_fire_on_trail_at_the_right_time_matches():
    path = [(28.6, 77.2, 0), (29.0, 76.8, 10), (29.5, 76.3, 20)]
    fires = [
        {"lat": 29.5, "lon": 76.35, "frp": 5, "time": NOW - timedelta(hours=18)},  # on trail
        {"lat": 29.5, "lon": 76.35, "frp": 5, "time": NOW - timedelta(hours=40)},  # too old
        {"lat": 25.0, "lon": 80.0, "frp": 5, "time": NOW - timedelta(hours=18)},   # far away
    ]
    hits = st.fires_on_trail(path, fires, NOW)
    assert len(hits) == 1
    assert hits[0]["trail_hours_ago"] == 20


def test_wind_fetch_retries_once_on_server_error(monkeypatch):
    calls = []

    class Res:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise st.requests.HTTPError(str(self.status_code))

        def json(self):
            return {"ok": True}

    def fake_get(url, params, timeout):
        calls.append(1)
        return Res(503 if len(calls) == 1 else 200)

    monkeypatch.setattr(st.requests, "get", fake_get)
    monkeypatch.setattr(st.time, "sleep", lambda s: None)
    assert st._get_json_with_retry("u", {}, "test") == {"ok": True}
    assert len(calls) == 2


def test_wind_fetch_gives_up_after_retry(monkeypatch):
    class Res:
        status_code = 503

        def raise_for_status(self):
            raise st.requests.HTTPError("503")

    monkeypatch.setattr(st.requests, "get", lambda url, params, timeout: Res())
    monkeypatch.setattr(st.time, "sleep", lambda s: None)
    with pytest.raises(st.UpstreamError):
        st._get_json_with_retry("u", {}, "test")


def test_corridor_widens_and_caps():
    assert st.corridor_km(0) == 15
    assert st.corridor_km(20) == 45
    assert st.corridor_km(100) == 75


def test_summary_groups_by_district_and_flags_stagnant_air():
    districts = [
        {"district": "Sangrur", "state": "Punjab", "lat": 30.25, "lon": 75.84},
        {"district": "Bathinda", "state": "Punjab", "lat": 30.21, "lon": 74.94},
    ]
    hits = [
        {"lat": 30.26, "lon": 75.85, "frp": 10.0},
        {"lat": 30.24, "lon": 75.80, "frp": 4.0},
        {"lat": 30.20, "lon": 74.95, "frp": 3.0},
        {"lat": 20.0, "lon": 70.0, "frp": 50.0},  # no district within range
    ]
    path = [(28.6, 77.2, 0), (28.65, 77.25, 1)]
    summary = st.summarize(path, hits, districts)
    assert summary["fire_count"] == 4
    assert [d["district"] for d in summary["top_districts"]] == ["Sangrur", "Bathinda"]
    assert summary["top_districts"][0]["fires"] == 2
    assert summary["stagnant"] is True
    assert hits[3]["district"] is None
    assert summary["other_fires"] == 1


def test_parse_fires_skips_low_confidence_and_bad_rows():
    text = (
        "latitude,longitude,bright_ti4,acq_date,acq_time,confidence,frp\n"
        "30.1,75.2,330,2026-10-08,0815,nominal,4.5\n"
        "30.2,75.3,330,2026-10-08,815,high,2.0\n"
        "30.3,75.4,330,2026-10-08,0815,low,9.9\n"
        "bad,75.4,330,2026-10-08,0815,nominal,1.0\n"
    )
    fires = st.parse_fires(text)
    assert len(fires) == 2
    assert fires[0]["time"] == datetime(2026, 10, 8, 8, 15, tzinfo=timezone.utc)
    assert fires[1]["time"].hour == 8  # "815" is zero-padded to 08:15


def test_get_smoke_trail_end_to_end(monkeypatch):
    monkeypatch.setattr(st, "_fetch_wind_grid", lambda la, lo: constant_grid(8, 315))
    fire = {"lat": 29.3, "lon": 76.5, "frp": 6.0, "time": NOW - timedelta(hours=12)}
    monkeypatch.setattr(st, "_fetch_fires", lambda: [fire])
    body = st.get_smoke_trail(28.6, 77.2, now=NOW)
    assert body["trail"][0] == [28.6, 77.2, 0]
    assert body["summary"]["hours_traced"] == 48
    assert body["summary"]["fire_count"] == 1
    assert body["fires"][0]["hours_ago"] == 12
    assert body["nearby_fires"] == [{"lat": 29.3, "lon": 76.5, "frp": 6.0}]


def test_endpoint_validates_and_returns_json(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "get_smoke_trail", lambda lat, lon: {"ok": [lat, lon]})
    client = app_module.app.test_client()
    assert client.get("/api/smoke-trail?lat=28.6&lon=77.2").get_json() == {"ok": [28.6, 77.2]}
    assert client.get("/api/smoke-trail?lat=28.6").status_code == 400


# ---------- Incoming Smoke Alert ----------

DELHI = (28.61, 77.21)
SANGRUR = {"district": "Sangrur", "state": "Punjab", "lat": 30.25, "lon": 75.84}


def fire(lat, lon, hours_ago, frp=5.0):
    return {"lat": lat, "lon": lon, "frp": frp, "time": NOW - timedelta(hours=hours_ago)}


def test_forward_trajectory_moves_downwind():
    # Wind FROM the north-west carries air TO the south-east.
    path = st.forward_trajectory(30.25, 75.84, constant_grid(12, 315, future=48), NOW, hours=10)
    lat, lon, h = path[-1]
    assert h == 10 and lat < 30.25 and lon > 75.84


def test_yesterdays_afternoon_pass_still_counts():
    # The latest daytime satellite pass can be ~28 h old when it's published.
    assert len(st.fire_clusters([fire(30.25, 75.84, 28)], NOW)) == 1


def test_nearby_fires_share_a_cluster_even_at_point_five():
    # Regression: round(60.5) == 60 but round(60.54) == 61 split these.
    clusters = st.fire_clusters([fire(30.25, 75.84, 1), fire(30.27, 75.86, 1)], NOW)
    assert len(clusters) == 1


def test_clusters_group_recent_fires_and_rank_by_intensity():
    fires = [fire(30.25, 75.84, 3, 4), fire(30.27, 75.86, 5, 6),   # same cell
             fire(29.15, 75.72, 2, 3),                              # another cell
             fire(30.25, 75.84, 40, 99)]                            # too old
    clusters = st.fire_clusters(fires, NOW)
    assert [c["fires"] for c in clusters] == [2, 1]
    assert clusters[0]["frp"] == 10.0


def test_north_west_wind_brings_punjab_smoke_to_delhi():
    # Delhi lies ~144° (SE) of Sangrur, so the wind must come FROM ~324°.
    grid = constant_grid(14, 324, future=48)
    result = st.smoke_forecast(*DELHI, grid, [fire(30.25, 75.84, 4, 8)], NOW, districts=[SANGRUR])
    alert = result["alert"]
    assert alert["incoming"] is True
    assert alert["districts"] == ["Sangrur"]
    # ~230 km at 14 km/h → roughly half a day (corridor widens with time)
    assert 8 <= alert["first_arrival_h"] <= 20
    assert alert["first_arrival_time"].startswith("2026-10-")


def test_south_east_wind_keeps_smoke_away():
    grid = constant_grid(14, 135, future=48)
    result = st.smoke_forecast(*DELHI, grid, [fire(30.25, 75.84, 4)], NOW, districts=[SANGRUR])
    assert result["alert"]["incoming"] is False
    assert result["clusters"][0]["arrival_h"] is None
    assert result["clusters"][0]["closest_km"] > 200


def test_local_fires_are_counted_separately():
    grid = constant_grid(14, 324, future=48)
    result = st.smoke_forecast(*DELHI, grid, [fire(28.62, 77.22, 2)], NOW, districts=[SANGRUR])
    assert result["local_fires"] == 1
    assert result["clusters"] == []


def test_forecast_endpoint(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "get_smoke_forecast", lambda lat, lon: {"alert": {"incoming": False}})
    client = app_module.app.test_client()
    assert client.get("/api/smoke-forecast?lat=28.6&lon=77.2").get_json() == {"alert": {"incoming": False}}
    assert client.get("/api/smoke-forecast").status_code == 400


# ---------- second weather model ----------

def test_models_agree_on_incoming_smoke_and_give_a_range():
    main = {"incoming": True, "first_arrival_h": 30, "fires": 27, "districts": ["Phalodi"]}
    gfs = {"incoming": True, "first_arrival_h": 21, "fires": 27, "districts": ["Phalodi"]}
    models = st.model_agreement(main, gfs)
    assert models["agree"] is True
    assert models["arrival_range_h"] == [21, 30]


def test_models_disagree_when_only_one_brings_smoke():
    main = {"incoming": True, "first_arrival_h": 30, "fires": 27, "districts": ["Phalodi"]}
    gfs = {"incoming": False, "first_arrival_h": None, "fires": 0, "districts": []}
    models = st.model_agreement(main, gfs)
    assert models["agree"] is False
    assert models["arrival_range_h"] is None
    assert models["second"]["incoming"] is False


def test_models_agree_on_no_smoke():
    none = {"incoming": False, "first_arrival_h": None, "fires": 0, "districts": []}
    models = st.model_agreement(none, dict(none))
    assert models["agree"] is True and models["arrival_range_h"] is None


def _forecast_with(monkeypatch, grids):
    def fake_grid(la, lo, model=None):
        grid = grids[model]
        if isinstance(grid, Exception):
            raise grid
        return grid
    monkeypatch.setattr(st, "_fetch_wind_grid", fake_grid)
    monkeypatch.setattr(st, "_fetch_fires", lambda: [fire(30.25, 75.84, 4, 8)])
    return st.get_smoke_forecast(*DELHI, now=NOW)


def test_forecast_reports_disagreement_between_models(monkeypatch):
    body = _forecast_with(monkeypatch, {
        None: constant_grid(14, 324, future=48),               # brings Punjab smoke to Delhi
        st.SECOND_MODEL: constant_grid(14, 135, future=48),    # blows it away
    })
    assert body["alert"]["incoming"] is True
    assert body["alert"]["models"]["agree"] is False


def test_forecast_still_works_if_second_model_fails(monkeypatch):
    body = _forecast_with(monkeypatch, {
        None: constant_grid(14, 324, future=48),
        st.SECOND_MODEL: st.UpstreamError("503"),
    })
    assert body["alert"]["incoming"] is True
    assert body["alert"]["models"] == {"checked": 1, "agree": None, "second": None, "arrival_range_h": None}


def test_far_away_fires_do_not_crowd_out_nearby_ones():
    # Regression (9 Oct): eight strong clusters outside the grid (e.g. Odisha,
    # Myanmar) took every top place, so the Punjab fire was never checked.
    far = [fire(20.0 + k, 95.0 + k, 3, frp=500) for k in range(8)]
    grid = constant_grid(14, 324, future=48)
    result = st.smoke_forecast(*DELHI, grid, far + [fire(30.25, 75.84, 4, 8)], NOW, districts=[SANGRUR])
    assert result["alert"]["incoming"] is True
    assert result["alert"]["districts"] == ["Sangrur"]
