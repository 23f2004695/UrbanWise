from datetime import datetime, timezone
from services import air, context
from services.air import UpstreamError
from services.advisory import DEFAULT_SLOTS
from tests.test_api import make_raw


def test_city_context_shape(monkeypatch):
    monkeypatch.setattr(air, "_fetch_air", lambda lat, lon: make_raw())
    monkeypatch.setattr(air, "_utcnow", lambda: datetime(2026, 10, 9, 10, 15, tzinfo=timezone.utc))
    monkeypatch.setattr(context, "get_smoke_trail", lambda lat, lon: {"summary": {
        "hours_traced": 48, "trail_km": 500, "stagnant": False, "fire_count": 3,
        "top_districts": [{"district": "Sangrur", "state": "Punjab", "fires": 2, "frp": 9.0}],
        "other_fires": 1,
    }})
    monkeypatch.setattr(context, "get_smoke_forecast", lambda lat, lon: {"alert": {
        "incoming": True, "first_arrival_time": "2026-10-09T20:00:00+00:00", "first_arrival_h": 34,
        "fires": 45, "districts": ["Phalodi"]}})
    ctx = context.city_context(28.6, 77.2, "Delhi", DEFAULT_SLOTS)
    assert ctx["city"] == "Delhi"
    assert ctx["air_now"]["aqi"] == 232
    assert len(ctx["forecast_next_48h"]) == 48
    assert [d["date"] for d in ctx["school_mode"]] == ["2026-10-09", "2026-10-10"]
    assert ctx["smoke_trail"]["top_districts"] == [{"district": "Sangrur", "state": "Punjab", "fires": 2}]
    assert ctx["local_time"]  # real clock in the city's timezone
    assert ctx["incoming_smoke_next_48h"]["source_districts"] == ["Phalodi"]


def test_city_context_survives_smoke_trail_failure(monkeypatch):
    monkeypatch.setattr(air, "_fetch_air", lambda lat, lon: make_raw())
    monkeypatch.setattr(air, "_utcnow", lambda: datetime(2026, 10, 9, 10, 15, tzinfo=timezone.utc))

    def boom(lat, lon):
        raise UpstreamError("down")

    monkeypatch.setattr(context, "get_smoke_trail", boom)
    monkeypatch.setattr(context, "get_smoke_forecast", boom)
    ctx = context.city_context(28.6, 77.2, "Delhi", DEFAULT_SLOTS)
    assert ctx["smoke_trail"] == "unavailable right now"
    assert ctx["incoming_smoke_next_48h"] == "unavailable right now"
