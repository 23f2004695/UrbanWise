from datetime import datetime, timedelta, timezone

import pytest

import pipeline
from services import smoke_trail as st
from services import store


@pytest.fixture
def s3(monkeypatch):
    """In-memory stand-in for the S3 bucket."""
    objects = {}
    monkeypatch.setenv("RESULTS_BUCKET", "test-bucket")
    monkeypatch.setattr(store, "get_json", lambda key: objects.get(key))
    monkeypatch.setattr(store, "put_json", lambda key, data: objects.__setitem__(key, data) or True)
    monkeypatch.setattr(pipeline, "PAUSE_S", 0)
    st._wind_cache.clear()
    return objects


def wind_body(n=49):
    return [{"hourly": {"time": ["2026-10-09T00:00"], "wind_speed_925hPa": [10],
                        "wind_direction_925hPa": [315]}} for _ in range(n)]


def test_stored_grid_is_used_instead_of_open_meteo(s3, monkeypatch):
    s3[st.wind_store_key(29.0, 77.0)] = {"fetched_at": datetime.now(timezone.utc).isoformat(), "body": wind_body()}
    monkeypatch.setattr(st, "download_wind", lambda *a: pytest.fail("should not call Open-Meteo"))
    grid = st._fetch_wind_grid(29.0, 77.0)
    assert grid.at(29.0, 77.0, datetime(2026, 10, 9, tzinfo=timezone.utc)) == (10, 315)


def test_old_stored_grid_is_refetched_and_shared(s3, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    s3[st.wind_store_key(29.0, 77.0)] = {"fetched_at": old.isoformat(), "body": wind_body()}
    calls = []
    monkeypatch.setattr(st, "download_wind", lambda *a: calls.append(a) or wind_body())
    st._fetch_wind_grid(29.0, 77.0)
    assert calls == [(29.0, 77.0, None)]
    assert s3[st.wind_store_key(29.0, 77.0)]["fetched_at"] > old.isoformat()


def test_no_bucket_means_no_store(monkeypatch):
    monkeypatch.delenv("RESULTS_BUCKET", raising=False)
    assert store.get_json("x") is None and store.put_json("x", {}) is False


def _fake_compute(monkeypatch, fail=()):
    def make(key):
        def compute(lat, lon):
            if key in fail:
                raise RuntimeError(f"{key} broke")
            return {"key": key, "lat": lat}
        return compute
    monkeypatch.setattr(pipeline, "get_air", make("air"))
    monkeypatch.setattr(pipeline, "get_smoke_trail", make("trail"))
    monkeypatch.setattr(pipeline, "get_smoke_forecast", make("forecast"))
    monkeypatch.setattr(st, "_fetch_fires", lambda: [
        {"lat": 30.0, "lon": 75.0, "frp": 3.0, "time": datetime(2026, 10, 9, 8, tzinfo=timezone.utc)}])


def test_pipeline_writes_latest_and_history(s3, monkeypatch):
    _fake_compute(monkeypatch)
    downloads = []
    monkeypatch.setattr(pipeline, "download_wind", lambda *a: downloads.append(a) or wind_body())
    now = datetime(2026, 10, 9, 14, 5, tzinfo=timezone.utc)
    report = pipeline.run(now=now, pause_s=0)

    assert len(report["cities"]) == len(pipeline.CITIES) and not report["errors"]
    assert len(downloads) == 2 * len(pipeline.CITIES)  # both weather models
    delhi = s3["latest/results/new-delhi.json"]
    assert delhi["air"]["key"] == "air" and delhi["smoke_forecast"]["key"] == "forecast"
    assert s3["history/2026-10-09/14/new-delhi.json"] == delhi
    assert s3["history/2026-10-09/14/fires.json"][0]["time"] == "2026-10-09T08:00:00+00:00"
    assert s3["latest/run.json"]["wind_downloads"] == 16


def test_fresh_grids_are_not_downloaded_again(s3, monkeypatch):
    _fake_compute(monkeypatch)
    now = datetime.now(timezone.utc)
    for _, _, lat, lon in pipeline.CITIES:
        for model in (None, st.SECOND_MODEL):
            s3[st.wind_store_key(float(round(lat)), float(round(lon)), model)] = {
                "fetched_at": (now - timedelta(hours=1)).isoformat(), "body": wind_body()}
    monkeypatch.setattr(pipeline, "download_wind", lambda *a: pytest.fail("grid is still fresh"))
    assert pipeline.run(now=now, pause_s=0)["wind_downloads"] == 0


def test_handler_fails_loudly_when_nothing_worked(s3, monkeypatch):
    _fake_compute(monkeypatch, fail=("air", "trail", "forecast"))
    monkeypatch.setattr(pipeline, "download_wind", lambda *a: wind_body())
    with pytest.raises(RuntimeError, match="no results"):
        pipeline.handler({}, None)


def test_one_broken_city_does_not_stop_the_rest(s3, monkeypatch):
    _fake_compute(monkeypatch, fail=("trail",))
    monkeypatch.setattr(pipeline, "download_wind", lambda *a: wind_body())
    report = pipeline.run(pause_s=0)
    assert len(report["cities"]) == len(pipeline.CITIES)
    assert any("smoke_trail" in e for e in report["errors"])
    assert s3["latest/results/ludhiana.json"]["smoke_trail"] is None
