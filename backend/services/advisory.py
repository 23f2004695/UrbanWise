"""Pure decision logic: CPCB AQI, GRAP stages and School Mode.

No network calls here, so everything is easy to unit-test.
"""

# CPCB National AQI breakpoints: (conc_lo, conc_hi, aqi_lo, aqi_hi).
# CPCB defines "Severe" as open-ended (PM2.5 250+, PM10 430+); the upper
# concentrations below are the convention used to scale it to 500.
PM25_BREAKPOINTS = [
    (0, 30, 0, 50),
    (31, 60, 51, 100),
    (61, 90, 101, 200),
    (91, 120, 201, 300),
    (121, 250, 301, 400),
    (251, 380, 401, 500),
]
PM10_BREAKPOINTS = [
    (0, 50, 0, 50),
    (51, 100, 51, 100),
    (101, 250, 101, 200),
    (251, 350, 201, 300),
    (351, 430, 301, 400),
    (431, 600, 401, 500),
]

CATEGORIES = [
    (50, "Good"),
    (100, "Satisfactory"),
    (200, "Moderate"),
    (300, "Poor"),
    (400, "Very Poor"),
    (500, "Severe"),
]

ADVICE = {
    "Good": "Air is clean. Enjoy outdoor activities.",
    "Satisfactory": "Air is acceptable. Very sensitive people should watch for symptoms.",
    "Moderate": "People with asthma, heart disease, children and the elderly should limit long outdoor exertion.",
    "Poor": "Avoid long or heavy outdoor exercise. Sensitive groups should stay indoors where possible.",
    "Very Poor": "Avoid outdoor activity. Keep windows closed and wear an N95 mask if you must go out.",
    "Severe": "Stay indoors. Everyone should avoid outdoor activity; wear an N95 mask if you must go out.",
}


def sub_index(conc, breakpoints):
    """Linear interpolation of a pollutant concentration onto the AQI scale."""
    if conc is None:
        return None
    conc = max(conc, 0)
    for c_lo, c_hi, i_lo, i_hi in breakpoints:
        if conc <= c_hi:
            # CPCB bands are integer-bounded (30 → 31); keep values in the gap
            # inside the lower band's top instead of dipping below i_lo.
            value = i_lo + (i_hi - i_lo) * (conc - c_lo) / (c_hi - c_lo)
            return max(i_lo, min(i_hi, value))
    return 500


def cpcb_aqi(pm25, pm10):
    """Return (aqi, dominant_pollutant) using the higher of the two sub-indices."""
    indices = {
        "pm25": sub_index(pm25, PM25_BREAKPOINTS),
        "pm10": sub_index(pm10, PM10_BREAKPOINTS),
    }
    indices = {k: v for k, v in indices.items() if v is not None}
    if not indices:
        return None, None
    dominant = max(indices, key=indices.get)
    return round(indices[dominant]), dominant


def category(aqi):
    for upper, name in CATEGORIES:
        if aqi <= upper:
            return name
    return "Severe"


def advice(aqi):
    return ADVICE[category(aqi)]


def grap_stage(aqi):
    """Graded Response Action Plan stage for Delhi-NCR (None below Stage I)."""
    if aqi > 450:
        return "IV"
    if aqi > 400:
        return "III"
    if aqi > 300:
        return "II"
    if aqi > 200:
        return "I"
    return None


# ---------- School Mode ----------

DEFAULT_SLOTS = [
    {"id": "assembly", "label": "Morning assembly", "time": "08:00"},
    {"id": "pe", "label": "PE / sports", "time": "11:00"},
    {"id": "dismissal", "label": "Dismissal", "time": "14:00"},
]


def school_decision(aqi):
    """Go / caution / limit / cancel for an outdoor school activity."""
    if aqi <= 100:
        return {"decision": "go", "verdict": "Go",
                "advice": "All outdoor activities can go ahead normally."}
    if aqi <= 200:
        return {"decision": "caution", "verdict": "Go with care",
                "advice": "Normal activities; children with asthma should avoid heavy exertion."}
    if aqi <= 300:
        return {"decision": "limit", "verdict": "Limit",
                "advice": "Move PE indoors and keep outdoor assembly short."}
    if aqi <= 400:
        return {"decision": "cancel", "verdict": "Cancel",
                "advice": "No outdoor activities. Keep classroom windows closed."}
    return {"decision": "cancel", "verdict": "Cancel",
            "advice": "Indoor only. Consider hybrid or online classes for primary grades."}


def day_aqi(forecast, date):
    """CPCB AQI from the day's average PM2.5/PM10 — the basis GRAP uses.

    Returns None when the forecast has no concentrations for that day.
    """
    hours = [f for f in forecast if f["time"].startswith(date)]
    pm25 = [f["pm25"] for f in hours if f.get("pm25") is not None]
    pm10 = [f["pm10"] for f in hours if f.get("pm10") is not None]
    if not pm25 and not pm10:
        return None
    aqi, _ = cpcb_aqi(sum(pm25) / len(pm25) if pm25 else None,
                      sum(pm10) / len(pm10) if pm10 else None)
    return aqi


def school_plan(forecast, dates, slots=DEFAULT_SLOTS):
    """Evaluate each school slot against the forecast for that exact hour.

    forecast: list of {"time": "YYYY-MM-DDTHH:00", "aqi": int, ...}
    dates:    list of "YYYY-MM-DD" strings (e.g. today and tomorrow)
    """
    by_time = {f["time"]: f for f in forecast}
    days = []
    for date in dates:
        entries = []
        worst_aqi = None
        for slot in slots:
            hour = by_time.get(f"{date}T{slot['time']}")
            if hour is None:
                entries.append({**slot, "aqi": None, "category": None,
                                "decision": "unknown", "verdict": "No data", "advice": ""})
                continue
            worst_aqi = hour["aqi"] if worst_aqi is None else max(worst_aqi, hour["aqi"])
            entries.append({**slot, "aqi": hour["aqi"], "category": category(hour["aqi"]),
                            **school_decision(hour["aqi"])})
        # GRAP is defined on the day's average, not on one bad hour.
        daily = day_aqi(forecast, date)
        basis = daily if daily is not None else worst_aqi
        days.append({
            "date": date,
            "slots": entries,
            "day_aqi": daily,
            "grap_stage": grap_stage(basis) if basis is not None else None,
        })
    return days
