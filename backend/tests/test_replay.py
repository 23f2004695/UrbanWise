"""Demo replay serves the captured 8 Oct 2026 snapshot, always labelled."""

import json
from pathlib import Path

import pytest

import app as app_module
from services import replay
from services.advisory import DEFAULT_SLOTS
from services.context import city_context

DATE = "2026-10-08"
DELHI = "lat=28.6139&lon=77.209"


@pytest.fixture
def client():
    return app_module.app.test_client()


def test_snapshot_exists_and_is_marked_not_live():
    m = json.loads((replay.ROOT / DATE / "manifest.json").read_text())
    assert "NOT live" in m["kind"]
    assert set(m["cities"]) == {"delhi", "ludhiana", "chandigarh"}
    assert replay.available() == [DATE]


@pytest.mark.parametrize("endpoint", ["air", "smoke-trail", "smoke-forecast", "radar"])
def test_replay_endpoints_serve_the_snapshot_with_a_marker(client, endpoint):
    res = client.get(f"/api/{endpoint}?{DELHI}&replay={DATE}")
    assert res.status_code == 200
    body = res.get_json()
    assert body["_replay"] == {"date": DATE, "captured_at_utc": "2026-10-08T12:09:44+00:00", "live": False}


def test_replay_preserves_the_delhi_alert(client):
    alert = client.get(f"/api/smoke-forecast?{DELHI}&replay={DATE}").get_json()["alert"]
    assert alert["incoming"] is True and alert["districts"] == ["Phalodi"] and alert["fires"] == 45


def test_replay_school_is_recomputed_with_custom_times(client):
    default = client.get(f"/api/school?{DELHI}&replay={DATE}").get_json()
    custom = client.get(f"/api/school?{DELHI}&replay={DATE}&pe=13:00").get_json()
    assert [d["date"] for d in default["days"]] == ["2026-10-08", "2026-10-09"]
    assert custom["days"][0]["slots"][1]["time"] == "13:00"
    assert custom["_replay"]["live"] is False


def test_nearby_coordinates_match_but_other_cities_are_404(client):
    assert client.get(f"/api/air?lat=28.7&lon=77.1&replay={DATE}").status_code == 200
    res = client.get(f"/api/air?lat=26.9196&lon=75.7878&replay={DATE}")  # Jaipur
    assert res.status_code == 404
    assert "only covers" in res.get_json()["error"]


@pytest.mark.parametrize("bad", ["2025-01-01", "../etc", "2026-10-08/x"])
def test_unknown_or_unsafe_replay_dates_are_400(client, bad):
    assert client.get(f"/api/air?{DELHI}&replay={bad}").status_code == 400


def test_live_requests_are_unaffected(client, monkeypatch):
    monkeypatch.setattr(app_module, "get_air", lambda lat, lon: {"live": True})
    assert client.get(f"/api/air?{DELHI}").get_json() == {"live": True}


def test_replay_context_for_the_assistant():
    ctx = city_context(28.6139, 77.209, "New Delhi", DEFAULT_SLOTS, replay_date=DATE)
    assert ctx["data_mode"].startswith("DEMO REPLAY")
    assert ctx["local_time"] == "2026-10-08 17:39"     # capture time in IST, not now
    assert ctx["incoming_smoke_next_48h"]["source_districts"] == ["Phalodi"]
    assert ctx["grap_applies_here"] is True


def test_replay_circular_uses_snapshot_dates(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(app_module, "generate_circular", lambda facts: seen.update(facts) or
                        {"en": "x", "hi": "y", "pa": "z", "model": "m", "fallback": False})
    res = client.post("/api/circular", json={"lat": 28.6139, "lon": 77.209, "replay": DATE})
    assert res.status_code == 200 and seen["date"] == "2026-10-09"   # "tomorrow" of the snapshot
