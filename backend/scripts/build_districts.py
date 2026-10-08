"""Regenerate data/districts.json: coordinates of district headquarter towns.

Smoke Trail labels fire clusters with the nearest district. Coordinates come
from the Open-Meteo geocoding API rather than being typed by hand.

Run from backend/:  python scripts/build_districts.py
"""

import json
import sys
from pathlib import Path

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# (district, headquarters town to geocode, state as Open-Meteo names it[, country code])
DISTRICTS = [
    # Punjab
    ("Amritsar", "Amritsar", "Punjab"),
    ("Barnala", "Barnala", "Punjab"),
    ("Bathinda", "Bathinda", "Punjab"),
    ("Faridkot", "Faridkot", "Punjab"),
    ("Fatehgarh Sahib", "Sirhind", "Punjab"),
    ("Fazilka", "Fazilka", "Punjab"),
    ("Ferozepur", "Firozpur", "Punjab"),
    ("Gurdaspur", "Gurdaspur", "Punjab"),
    ("Hoshiarpur", "Hoshiarpur", "Punjab"),
    ("Jalandhar", "Jalandhar", "Punjab"),
    ("Kapurthala", "Kapurthala", "Punjab"),
    ("Ludhiana", "Ludhiana", "Punjab"),
    ("Malerkotla", "Maler Kotla", "Punjab"),
    ("Mansa", "Mansa", "Punjab"),
    ("Moga", "Moga", "Punjab"),
    ("Sri Muktsar Sahib", "Muktsar", "Punjab"),
    ("Pathankot", "Pathankot", "Punjab"),
    ("Patiala", "Patiala", "Punjab"),
    ("Rupnagar", "Ropar", "Punjab"),
    ("SAS Nagar (Mohali)", "Mohali", "Punjab"),
    ("Sangrur", "Sangrur", "Punjab"),
    ("Shaheed Bhagat Singh Nagar", "Nawanshahr", "Punjab"),
    ("Tarn Taran", "Tarn Taran", "Punjab"),
    # Haryana
    ("Ambala", "Ambala", "Haryana"),
    ("Bhiwani", "Bhiwani", "Haryana"),
    ("Charkhi Dadri", "Charkhi Dadri", "Haryana"),
    ("Faridabad", "Faridabad", "Haryana"),
    ("Fatehabad", "Fatehabad", "Haryana"),
    ("Gurugram", "Gurugram", "Haryana"),
    ("Hisar", "Hisar", "Haryana"),
    ("Jhajjar", "Jhajjar", "Haryana"),
    ("Jind", "Jind", "Haryana"),
    ("Kaithal", "Kaithal", "Haryana"),
    ("Karnal", "Karnal", "Haryana"),
    ("Kurukshetra", "Thanesar", "Haryana"),
    ("Mahendragarh", "Narnaul", "Haryana"),
    ("Nuh", "Nuh", "Haryana"),
    ("Palwal", "Palwal", "Haryana"),
    ("Panchkula", "Panchkula", "Haryana"),
    ("Panipat", "Panipat", "Haryana"),
    ("Rewari", "Rewari", "Haryana"),
    ("Rohtak", "Rohtak", "Haryana"),
    ("Sirsa", "Sirsa", "Haryana"),
    ("Sonipat", "Sonipat", "Haryana"),
    ("Yamunanagar", "Yamunanagar", "Haryana"),
    # Delhi
    ("Delhi", "Delhi", "National Capital Territory of Delhi"),
    # Western Uttar Pradesh
    ("Aligarh", "Aligarh", "Uttar Pradesh"),
    ("Baghpat", "Baghpat", "Uttar Pradesh"),
    ("Bulandshahr", "Bulandshahr", "Uttar Pradesh"),
    ("Ghaziabad", "Ghaziabad", "Uttar Pradesh"),
    ("Mathura", "Mathura", "Uttar Pradesh"),
    ("Meerut", "Meerut", "Uttar Pradesh"),
    ("Muzaffarnagar", "Muzaffarnagar", "Uttar Pradesh"),
    ("Saharanpur", "Saharanpur", "Uttar Pradesh"),
    ("Shamli", "Shamli", "Uttar Pradesh"),
    # Northern Rajasthan
    ("Sri Ganganagar", "Sri Ganganagar", "Rajasthan"),
    ("Hanumangarh", "Hanumangarh", "Rajasthan"),
    # Rest of Rajasthan (westerly winds often cross it on the way to Delhi)
    ("Bikaner", "Bikaner", "Rajasthan"),
    ("Churu", "Churu", "Rajasthan"),
    ("Jhunjhunu", "Jhunjhunun", "Rajasthan"),
    ("Sikar", "Sikar", "Rajasthan"),
    ("Nagaur", "Nagaur", "Rajasthan"),
    ("Jodhpur", "Jodhpur", "Rajasthan"),
    ("Phalodi", "Phalodi", "Rajasthan"),
    ("Jaisalmer", "Jaisalmer", "Rajasthan"),
    ("Barmer", "Barmer", "Rajasthan"),
    ("Pali", "Pali", "Rajasthan"),
    ("Ajmer", "Ajmer", "Rajasthan"),
    ("Jaipur", "Jaipur", "Rajasthan"),
    ("Alwar", "Alwar", "Rajasthan"),
    ("Bharatpur", "Bharatpur", "Rajasthan"),
    ("Tonk", "Tonk", "Rajasthan"),
    ("Kota", "Kota", "Rajasthan"),
    # More of Uttar Pradesh and northern Madhya Pradesh
    ("Agra", "Agra", "Uttar Pradesh"),
    ("Moradabad", "Moradabad", "Uttar Pradesh"),
    ("Bijnor", "Bijnor", "Uttar Pradesh"),
    ("Bareilly", "Bareilly", "Uttar Pradesh"),
    ("Gwalior", "Gwalior", "Madhya Pradesh"),
    ("Morena", "Morena", "Madhya Pradesh"),
    # Punjab, Pakistan (cross-border stubble burning)
    ("Lahore", "Lahore", "Punjab", "PK"),
    ("Kasur", "Kasur", "Punjab", "PK"),
    ("Okara", "Okara", "Punjab", "PK"),
    ("Sahiwal", "Sahiwal", "Punjab", "PK"),
    ("Pakpattan", "Pakpattan", "Punjab", "PK"),
    ("Bahawalnagar", "Bahawalnagar", "Punjab", "PK"),
    ("Vehari", "Vehari", "Punjab", "PK"),
    ("Bahawalpur", "Bahawalpur", "Punjab", "PK"),
    ("Multan", "Multan", "Punjab", "PK"),
    ("Faisalabad", "Faisalabad", "Punjab", "PK"),
    ("Gujranwala", "Gujranwala", "Punjab", "PK"),
    ("Sialkot", "Sialkot", "Punjab", "PK"),
    ("Narowal", "Narowal", "Punjab", "PK"),
]


def geocode(town, state, country="IN"):
    res = requests.get(
        GEOCODE_URL,
        params={"name": town, "count": 10, "countryCode": country, "language": "en"},
        timeout=10,
    )
    res.raise_for_status()
    matches = [r for r in res.json().get("results", []) if r.get("admin1") == state]
    # Prefer the most populous match (the town itself, not a same-named village).
    # Matches without a population figure are usually villages, not the
    # district town, so they are rejected rather than silently used.
    matches = [r for r in matches if r.get("population")]
    matches.sort(key=lambda r: r["population"], reverse=True)
    return matches[0] if matches else None


def main():
    out, missing = [], []
    for district, town, state, *country in DISTRICTS:
        country = country[0] if country else "IN"
        hit = geocode(town, state, country)
        if hit is None:
            missing.append(f"{district} ({town}, {state}, {country})")
            continue
        label = "Delhi" if state.startswith("National Capital") else state
        if country == "PK":
            label = f"{state} (Pakistan)"
        out.append({
            "district": district,
            "state": label,
            "lat": round(hit["latitude"], 4),
            "lon": round(hit["longitude"], 4),
        })
    path = Path(__file__).resolve().parent.parent / "data" / "districts.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(f"Wrote {len(out)} districts to {path}")
    if missing:
        print("Not found:", ", ".join(missing), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
