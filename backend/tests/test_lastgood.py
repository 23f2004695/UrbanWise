from datetime import datetime, timedelta, timezone

import pytest

import app as app_module
from services import air, lastgood, smoke_trail
from services.air import UpstreamError
from tests.test_api import make_raw


def flaky(results):
    """A fetch that returns or raises the given results in order."""
    calls = iter(results)

    def fetch(*args):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result
    return fetch


def test_serves_last_good_copy_when_the_provider_fails():
    fetch = lastgood.keep_last_good("test", (UpstreamError,))(
        flaky([{"pm": 1}, UpstreamError("429")]))
    assert fetch(1, 2) == {"pm": 1}
    stale = fetch(1, 2)
    assert stale["pm"] == 1 and stale["_stale_since"]
    assert lastgood.stale_info(stale)["age_min"] == 0


def test_no_saved_copy_means_the_error_still_shows():
    fetch = lastgood.keep_last_good("test", (UpstreamError,))(flaky([UpstreamError("503")]))
    with pytest.raises(UpstreamError):
        fetch(1, 2)


def test_copies_are_per_place():
    fetch = lastgood.keep_last_good("test", (UpstreamError,))(
        flaky([{"city": "a"}, UpstreamError("429")]))
    fetch("a")
    with pytest.raises(UpstreamError):
        fetch("b")


def test_other_errors_are_not_hidden():
    fetch = lastgood.keep_last_good("test", (UpstreamError,))(flaky([{"ok": 1}, KeyError("bug")]))
    fetch(1)
    with pytest.raises(KeyError):
        fetch(1)


def test_lists_and_objects_are_marked_without_changing_the_original():
    fires = [{"lat": 1}]
    marked = lastgood.mark_stale(fires, "2026-10-08T10:00:00+00:00")
    assert marked == fires and lastgood.stale_since(marked) and lastgood.stale_since(fires) is None

    grid = smoke_trail.WindGrid([0], [0], ["t"], {})
    marked = lastgood.mark_stale(grid, "2026-10-08T10:00:00+00:00")
    assert lastgood.stale_since(marked) and lastgood.stale_since(grid) is None


def test_stale_info_reports_the_oldest_input():
    now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    a = lastgood.mark_stale({}, (now - timedelta(minutes=30)).isoformat())
    b = lastgood.mark_stale([], (now - timedelta(hours=2)).isoformat())
    assert lastgood.stale_info(a, b, {}, now=now)["age_min"] == 120
    assert lastgood.stale_info({}, [], now=now) is None


def test_air_endpoint_keeps_working_through_an_outage(monkeypatch):
    class Ok:
        def raise_for_status(self):
            pass

        def json(self):
            return make_raw()

    monkeypatch.setattr(air.requests, "get", lambda *a, **k: Ok())
    client = app_module.app.test_client()
    first = client.get("/api/air?lat=28.6&lon=77.2").get_json()
    assert "stale" not in first

    def busy(*a, **k):
        raise air.requests.HTTPError("429 Too Many Requests")

    air._air_cache.clear()  # cache expired, provider now busy
    monkeypatch.setattr(air.requests, "get", busy)
    res = client.get("/api/air?lat=28.6&lon=77.2")
    assert res.status_code == 200
    assert res.get_json()["current"] == first["current"]
    assert res.get_json()["stale"]["age_min"] == 0
