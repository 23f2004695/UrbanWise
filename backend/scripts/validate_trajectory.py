"""Compare our back-trajectory with a NOAA HYSPLIT one for the same city and time.

Usage (from backend/):
    venv/bin/python scripts/validate_trajectory.py --name "New Delhi" \
        --lat 28.6139 --lon 77.209 --start 2026-10-08T12 \
        --hysplit ../docs/validation/hysplit_delhi.txt \
        --svg ../docs/validation/delhi.svg

--start is the UTC hour the trajectory starts from. The HYSPLIT file is the
trajectory endpoints text ("tdump") from the READY web tool.
Prints one markdown table row: distance between the two paths at 6/12/24/36/48 h.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from services.smoke_trail import (  # noqa: E402
    WIND_URL, WindGrid, _grid_axis, back_trajectory, haversine_km,
)

CHECK_HOURS = [6, 12, 24, 36, 48]


def wind_grid_for(lat, lon, start, model=None):
    """Same grid as the app, but for a fixed window ending at `start`.

    model=None uses the app's default (Open-Meteo best match); "gfs_seamless"
    uses the same weather model as HYSPLIT's GFS runs.
    """
    lats, lons = _grid_axis(float(round(lat))), _grid_axis(float(round(lon)))
    points = [(la, lo) for la in lats for lo in lons]
    params = {
        "latitude": ",".join(str(p[0]) for p in points),
        "longitude": ",".join(str(p[1]) for p in points),
        "hourly": "wind_speed_925hPa,wind_direction_925hPa",
        "wind_speed_unit": "kmh",
        "timezone": "UTC",
        "start_date": (start - timedelta(days=2)).date().isoformat(),
        "end_date": start.date().isoformat(),
    }
    if model:
        params["models"] = model
    # One-off script, so it can wait longer than the app does.
    res = requests.get(WIND_URL, params=params, timeout=90)
    res.raise_for_status()
    body = res.json()
    samples = {
        (n // len(lons), n % len(lons)): (loc["hourly"]["wind_speed_925hPa"], loc["hourly"]["wind_direction_925hPa"])
        for n, loc in enumerate(body)
    }
    return WindGrid(lats, lons, body[0]["hourly"]["time"], samples)


def read_tdump(path):
    """HYSPLIT endpoints → {hours_back: (lat, lon)} for the first trajectory."""
    lines = Path(path).read_text().splitlines()
    # Data rows follow the line listing the diagnostic variables (e.g. "1 PRESSURE").
    start = next(i for i, line in enumerate(lines) if "PRESSURE" in line.upper()) + 1
    points = {}
    for line in lines[start:]:
        cols = line.split()
        if len(cols) < 12 or cols[0] != "1":
            continue
        age, lat, lon = float(cols[8]), float(cols[9]), float(cols[10])
        points[round(abs(age))] = (lat, lon)
    return points


def svg(name, ours, theirs, city):
    """Both paths on a plain lat/lon plot (no map tiles, no extra libraries)."""
    pts = [(p[0], p[1]) for p in ours] + list(theirs.values()) + [city]
    lat_lo, lat_hi = min(p[0] for p in pts) - 0.5, max(p[0] for p in pts) + 0.5
    lon_lo, lon_hi = min(p[1] for p in pts) - 0.5, max(p[1] for p in pts) + 0.5
    w = 520
    h = round(w * (lat_hi - lat_lo) / (lon_hi - lon_lo))
    h = max(240, min(h, 640))

    def xy(lat, lon):
        return (round((lon - lon_lo) / (lon_hi - lon_lo) * w, 1),
                round((lat_hi - lat) / (lat_hi - lat_lo) * h, 1))

    def line(points, colour, dash=""):
        d = " ".join(f"{x},{y}" for x, y in (xy(*p) for p in points))
        return f'<polyline points="{d}" fill="none" stroke="{colour}" stroke-width="2.5" {dash}/>'

    def marks(points, colour):
        out = []
        for hours, (lat, lon) in points:
            if hours in CHECK_HOURS:
                x, y = xy(lat, lon)
                out.append(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{colour}"/>'
                           f'<text x="{x + 5}" y="{y - 5}" font-size="11" fill="{colour}">{hours}h</text>')
        return "".join(out)

    hy = sorted(theirs.items())
    cx, cy = xy(*city)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h + 30}" font-family="sans-serif">'
        f'<rect width="{w}" height="{h + 30}" fill="#fff"/>'
        + line([(p[0], p[1]) for p in ours], "#C2410C")
        + line([p for _, p in hy], "#1D4ED8", 'stroke-dasharray="6 4"')
        + marks([(p[2], (p[0], p[1])) for p in ours], "#C2410C")
        + marks(hy, "#1D4ED8")
        + f'<circle cx="{cx}" cy="{cy}" r="5" fill="#111"/>'
        # Name goes on whichever side of the dot has room.
        + (f'<text x="{cx - 8}" y="{cy - 8}" text-anchor="end"' if cx > w * 0.7 else f'<text x="{cx + 7}" y="{cy + 4}"')
        + f' font-size="12" font-weight="bold">{name}</text>'
        f'<text x="8" y="{h + 20}" font-size="12"><tspan fill="#C2410C">— UrbanWise</tspan>'
        f'<tspan fill="#1D4ED8" dx="14">- - NOAA HYSPLIT</tspan>'
        f'<tspan fill="#555" dx="14">lat {lat_lo:.1f}–{lat_hi:.1f}, lon {lon_lo:.1f}–{lon_hi:.1f}</tspan></text>'
        "</svg>\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", required=True, help="UTC hour, e.g. 2026-10-08T12")
    ap.add_argument("--hysplit", required=True, help="HYSPLIT tdump text file")
    ap.add_argument("--svg", help="write a comparison plot here")
    ap.add_argument("--model", help='Open-Meteo weather model, e.g. gfs_seamless (default: the app\'s best match)')
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
    ours = back_trajectory(args.lat, args.lon, wind_grid_for(args.lat, args.lon, start, args.model), start)
    theirs = read_tdump(args.hysplit)
    by_hour = {p[2]: (p[0], p[1]) for p in ours}

    cells = []
    for hours in CHECK_HOURS:
        if hours in by_hour and hours in theirs:
            cells.append(f"{round(haversine_km(*by_hour[hours], *theirs[hours]))} km")
        else:
            cells.append("n/a")
    ours_len = sum(haversine_km(a[0], a[1], b[0], b[1]) for a, b in zip(ours, ours[1:]))
    print(f"| {args.name} | {args.model or 'best match (app)'} | " + " | ".join(cells) + f" | {round(ours_len)} km |")

    if args.svg:
        Path(args.svg).write_text(svg(args.name, ours, theirs, (args.lat, args.lon)))


if __name__ == "__main__":
    main()
