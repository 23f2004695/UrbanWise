"""A code-only clone has no replay snapshot; the app must handle that cleanly."""

import app as app_module
from services import replay


def test_missing_snapshot_is_handled(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "ROOT", tmp_path / "missing")
    replay._manifest.cache_clear()
    try:
        client = app_module.app.test_client()
        assert replay.available() == []
        assert client.get("/api/replays").get_json() == {"dates": []}
        res = client.get("/api/air?lat=28.6139&lon=77.209&replay=2026-10-08")
        assert res.status_code == 400 and "No demo replay" in res.get_json()["error"]
    finally:
        replay._manifest.cache_clear()
