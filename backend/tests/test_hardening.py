"""Regression tests for the bug-hunt fixes (8 Oct)."""

import threading
from datetime import datetime, timezone

import pytest

import app as app_module
from services import air, ratelimit, smoke_trail
from services.air import UpstreamError
from tests.test_api import make_raw


@pytest.fixture
def client():
    for limiter in app_module.LIMITS.values():
        limiter._hits.clear()
    return app_module.app.test_client()


# --- request validation: clean 400s instead of 500s ---

@pytest.mark.parametrize("path", ["/api/speak", "/api/chat", "/api/circular"])
def test_non_object_json_body_is_400(client, path):
    assert client.post(path, json=["x"]).status_code == 400


def test_non_string_slot_time_is_400(client):
    body = {"lat": 28.6, "lon": 77.2, "message": "hi", "times": {"pe": 830}}
    res = client.post("/api/chat", json=body)
    assert res.status_code == 400 and "pe" in res.get_json()["error"]


def test_oversized_body_is_rejected(client):
    res = client.post("/api/speak", data=b"x" * (70 * 1024), content_type="application/json")
    assert res.status_code == 413


def test_unknown_route_returns_json_404(client):
    res = client.get("/api/nope")
    assert res.status_code == 404 and "error" in res.get_json()


# --- upstream problems are 502s, not 500s or misleading 400s ---

def test_null_air_arrays_are_a_502(client, monkeypatch):
    raw = make_raw()
    raw["hourly"]["pm2_5"] = None
    monkeypatch.setattr(air, "_fetch_air", lambda lat, lon: raw)
    assert client.get("/api/air?lat=28.6&lon=77.2").status_code == 502
    assert client.get("/api/school?lat=28.6&lon=77.2").status_code == 502


def test_garbage_geocoder_response_is_a_502(client, monkeypatch):
    class Garbage:
        def raise_for_status(self):
            pass

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    air._geo_cache.clear()
    monkeypatch.setattr(air.requests, "get", lambda *a, **k: Garbage())
    res = client.get("/api/geocode?q=Delhi")
    assert res.status_code == 502
    assert "Expecting value" not in res.get_json()["error"]  # internals not leaked


def test_unexpected_crash_is_generic_json_500(client, monkeypatch):
    def boom(lat, lon):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(app_module, "get_air", boom)
    res = client.get("/api/air?lat=28.6&lon=77.2")
    assert res.status_code == 500
    assert "secret" not in res.get_json()["error"]


# --- rate limiting on Gemini endpoints ---

def test_limiter_window():
    lim = ratelimit.RateLimiter(2, 60)
    assert lim.allow("a", 0) and lim.allow("a", 1)
    assert not lim.allow("a", 2)
    assert lim.allow("b", 2)          # per visitor
    assert lim.allow("a", 61.5)       # window slides


def test_speak_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(app_module, "synthesize", lambda text: (b"RIFF", []))
    codes = [client.post("/api/speak", json={"text": f"t{i}"}).status_code for i in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]


# --- thread safety: parallel callers neither crash nor duplicate fetches ---

def test_parallel_cache_misses_fetch_once(monkeypatch):
    calls = []

    class Res:
        def raise_for_status(self):
            pass

        def json(self):
            return make_raw()

    def slow_get(*args, **kwargs):
        calls.append(1)
        import time
        time.sleep(0.2)
        return Res()

    air._air_cache.clear()
    monkeypatch.setattr(air.requests, "get", slow_get)
    results, errors = [], []

    def worker():
        try:
            results.append(air._fetch_air(1.23, 4.56))
        except Exception as exc:  # the old unlocked cache raised KeyError/RuntimeError here
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == [] and len(results) == 8
    assert len(calls) == 1          # 8 simultaneous callers, one download


# --- data handling ---

def test_single_letter_low_confidence_is_skipped():
    text = ("latitude,longitude,acq_date,acq_time,confidence,frp\n"
            "30.1,75.2,2026-10-08,0815,l,4.5\n30.2,75.3,2026-10-08,0815,n,2.0\n")
    assert len(smoke_trail.parse_fires(text)) == 1


def test_school_today_uses_the_real_clock_after_midnight(monkeypatch):
    # Cached data still says 23:00 on the 8th, but it's already 00:15 IST on the 9th.
    raw = make_raw(now="2026-10-08T23:00")
    raw["utc_offset_seconds"] = 19800
    monkeypatch.setattr(air, "_fetch_air", lambda lat, lon: raw)
    monkeypatch.setattr(air, "_utcnow", lambda: datetime(2026, 10, 8, 18, 45, tzinfo=timezone.utc))
    _, today = air.get_school_hours(28.6, 77.2)
    assert today == "2026-10-09"


def test_best_hour_window_is_24_hours_even_with_gaps():
    raw = make_raw()
    times = raw["hourly"]["time"]
    # Remove 6 hours of data tomorrow morning, and make 15:00 the day after the cleanest.
    for h in range(6, 12):
        raw["hourly"]["pm2_5"][times.index(f"2026-10-10T{h:02d}:00")] = None
        raw["hourly"]["pm10"][times.index(f"2026-10-10T{h:02d}:00")] = None
    raw["hourly"]["pm2_5"][times.index("2026-10-10T15:00")] = 5   # > 24 h after 10:00 on the 9th
    report = air.build_air_report(raw)
    assert report["best_hour"]["time"] != "2026-10-10T15:00"
