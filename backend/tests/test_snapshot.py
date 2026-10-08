import pytest

from services import snapshot
from services.air import UpstreamError


@pytest.fixture(autouse=True)
def clear_cache():
    snapshot._snapshot_cache.clear()


def test_count_fires_uses_the_box():
    fires = [{"lat": 30.2, "lon": 75.8}, {"lat": 30.2, "lon": 80.0}, {"lat": 20.0, "lon": 75.8}]
    assert snapshot.count_fires(fires) == 1


def test_snapshot_skips_failed_cities(monkeypatch):
    def fake_air(lat, lon):
        if lat == snapshot.CITIES[0][2]:
            raise UpstreamError("down")
        return {"current": {"aqi": 150, "category": "Moderate"}}

    monkeypatch.setattr(snapshot, "get_air", fake_air)
    monkeypatch.setattr(snapshot, "_fetch_fires", lambda: [{"lat": 30.2, "lon": 75.8}])
    snap = snapshot.get_snapshot()
    assert len(snap["cities"]) == len(snapshot.CITIES) - 1
    assert snap["fires_48h_punjab_haryana"] == 1


def test_snapshot_fails_only_when_everything_fails(monkeypatch):
    def boom(*args):
        raise UpstreamError("down")

    monkeypatch.setattr(snapshot, "get_air", boom)
    monkeypatch.setattr(snapshot, "_fetch_fires", boom)
    with pytest.raises(UpstreamError):
        snapshot.get_snapshot()
