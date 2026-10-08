"""Capture a dated replay snapshot of real data for the demo.

Saves, for a few cities, the exact API responses the app shows AND every raw
upstream response used to compute them (NASA FIRMS, Open-Meteo), so the
snapshot is reproducible and can be checked later. This is a REPLAY dataset:
it is never presented as live data.

Run from backend/:  python scripts/capture_snapshot.py
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CITIES = {
    "delhi": {"name": "New Delhi", "region": "Delhi", "lat": 28.6139, "lon": 77.209},
    "ludhiana": {"name": "Ludhiana", "region": "Punjab", "lat": 30.912, "lon": 75.8538},
    "chandigarh": {"name": "Chandigarh", "region": "Chandigarh", "lat": 30.7363, "lon": 76.7884},
}
ENDPOINTS = ["air", "school", "smoke-trail", "smoke-forecast", "radar"]

# Record every upstream response the services make during capture.
_real_get = requests.get
raw_log = []


def recording_get(url, params=None, **kwargs):
    res = _real_get(url, params=params, **kwargs)
    raw_log.append({"url": url, "params": params, "status": res.status_code, "text": res.text})
    return res


def main():
    requests.get = recording_get
    import app as app_module  # imported after patching so services use the recorder

    captured_at = datetime.now(timezone.utc).replace(microsecond=0)
    day = captured_at.astimezone().date().isoformat()
    out = Path(__file__).resolve().parent.parent / "data" / "replay" / day
    (out / "api").mkdir(parents=True, exist_ok=True)
    (out / "raw").mkdir(parents=True, exist_ok=True)

    client = app_module.app.test_client()
    files = {}
    for key, city in CITIES.items():
        for ep in ENDPOINTS:
            res = client.get(f"/api/{ep}?lat={city['lat']}&lon={city['lon']}")
            if res.status_code != 200:
                raise SystemExit(f"{ep} for {key} failed: {res.status_code} {res.get_data(as_text=True)[:200]}")
            path = out / "api" / f"{key}.{ep}.json"
            path.write_text(json.dumps(res.get_json(), ensure_ascii=False, separators=(",", ":")))
            files[f"{key}.{ep}"] = path.name
            print(f"  {key:10} {ep:15} {path.stat().st_size // 1024} KB")

    raw_index = []
    for i, r in enumerate(raw_log):
        ext = "csv" if r["url"].endswith(".csv") else "json"
        name = f"{i:02d}.{ext}"
        (out / "raw" / name).write_text(r["text"])
        raw_index.append({
            "file": f"raw/{name}", "url": r["url"], "params": r["params"], "status": r["status"],
            "sha256": hashlib.sha256(r["text"].encode()).hexdigest(),
        })

    manifest = {
        "kind": "UrbanWise demo replay snapshot — NOT live data",
        "captured_at_utc": captured_at.isoformat(),
        "cities": CITIES,
        "api": files,
        "raw": raw_index,
        "sources": {
            "air_quality": "Open-Meteo Air Quality API (CAMS global model estimates)",
            "wind": "Open-Meteo Forecast API, 925 hPa winds (model)",
            "fires": "NASA FIRMS, VIIRS S-NPP NRT, South Asia 48 h (satellite thermal anomalies)",
        },
        "note": "Outputs were produced by UrbanWise's own code at capture time. Smoke paths "
                "and arrival times are model-based estimates.",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    total = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"Saved {len(files)} API responses and {len(raw_index)} raw upstream responses "
          f"to {out} ({total // 1024} KB), captured {captured_at.isoformat()}")


if __name__ == "__main__":
    main()
