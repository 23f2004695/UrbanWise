import pytest

from services.advisory import (
    category, cpcb_aqi, grap_stage, school_decision, school_plan,
)


@pytest.mark.parametrize("pm25, expected", [
    (0, 0),
    (30, 50),
    (31, 51),
    (60, 100),
    (90, 200),
    (120, 300),
    (250, 400),
    (380, 500),
    (999, 500),
])
def test_pm25_band_edges(pm25, expected):
    aqi, dominant = cpcb_aqi(pm25, None)
    assert aqi == expected
    assert dominant == "pm25"


@pytest.mark.parametrize("pm10, expected", [
    (50, 50), (100, 100), (250, 200), (350, 300), (430, 400),
])
def test_pm10_band_edges(pm10, expected):
    assert cpcb_aqi(None, pm10) == (expected, "pm10")


def test_value_in_integer_gap_stays_in_band():
    # 30.5 sits between CPCB's 30 and 31 boundaries; must not dip below 51.
    aqi, _ = cpcb_aqi(30.5, None)
    assert aqi == 51


def test_dominant_pollutant_is_the_higher_sub_index():
    # PM2.5 75 → ~150, PM10 300 → ~250
    aqi, dominant = cpcb_aqi(75, 300)
    assert dominant == "pm10"
    assert aqi == 250


def test_no_data_returns_none():
    assert cpcb_aqi(None, None) == (None, None)


@pytest.mark.parametrize("aqi, name", [
    (0, "Good"), (50, "Good"), (51, "Satisfactory"), (101, "Moderate"),
    (201, "Poor"), (301, "Very Poor"), (401, "Severe"), (500, "Severe"),
])
def test_category(aqi, name):
    assert category(aqi) == name


@pytest.mark.parametrize("aqi, stage", [
    (200, None), (201, "I"), (301, "II"), (401, "III"), (451, "IV"),
])
def test_grap_stage(aqi, stage):
    assert grap_stage(aqi) == stage


@pytest.mark.parametrize("aqi, decision", [
    (100, "go"), (101, "caution"), (201, "limit"), (301, "cancel"), (450, "cancel"),
])
def test_school_decision(aqi, decision):
    assert school_decision(aqi)["decision"] == decision


def test_school_plan_uses_each_slots_own_hour():
    forecast = [
        {"time": "2026-10-09T08:00", "aqi": 320},
        {"time": "2026-10-09T11:00", "aqi": 180},
        {"time": "2026-10-09T14:00", "aqi": 90},
    ]
    [day] = school_plan(forecast, ["2026-10-09"])
    decisions = [s["decision"] for s in day["slots"]]
    assert decisions == ["cancel", "caution", "go"]
    # Activity name must survive alongside the verdict.
    assert day["slots"][0]["label"] == "Morning assembly"
    assert day["slots"][0]["verdict"] == "Cancel"
    assert day["grap_stage"] == "II"  # driven by the worst slot


def test_school_plan_marks_missing_hours():
    [day] = school_plan([], ["2026-10-09"])
    assert all(s["decision"] == "unknown" for s in day["slots"])
    assert day["grap_stage"] is None


def test_grap_uses_the_day_average_not_one_bad_hour():
    # One rush-hour spike (PM2.5 125 → ~Very Poor) on an otherwise moderate day.
    hours = [{"time": f"2026-10-09T{h:02d}:00", "pm25": 125 if h == 8 else 70, "pm10": None,
              "aqi": cpcb_aqi(125 if h == 8 else 70, None)[0]} for h in range(24)]
    [day] = school_plan(hours, ["2026-10-09"])
    assert day["slots"][0]["decision"] == "cancel"          # the 8 am slot itself is still flagged
    assert day["day_aqi"] == cpcb_aqi((125 + 23 * 70) / 24, None)[0]
    assert day["grap_stage"] is None                         # daily level ~Moderate: no GRAP stage


@pytest.mark.parametrize("name, lat, lon, inside", [
    ("Delhi", 28.6139, 77.209, True), ("Gurugram", 28.4601, 77.0263, True),
    ("Noida", 28.5355, 77.391, True), ("Meerut", 28.98, 77.7064, True), ("Panipat", 29.3875, 76.9682, True),
    ("Agra", 27.1833, 78.0167, False), ("Ludhiana", 30.912, 75.8538, False),
    ("Chandigarh", 30.7363, 76.7884, False), ("Jaipur", 26.9196, 75.7878, False),
])
def test_delhi_ncr_approximation(name, lat, lon, inside):
    from services.advisory import in_delhi_ncr
    assert in_delhi_ncr(lat, lon) is inside, name
