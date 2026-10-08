# Checking our trajectories against NOAA HYSPLIT

Smoke Trail and the Incoming Smoke Alert both depend on our simple trajectory model (see [METHODS.md](METHODS.md)). To see how far off it is, we compared it with [NOAA HYSPLIT](https://www.ready.noaa.gov/HYSPLIT.php), the trajectory model most air quality researchers use.

## Setup

- **Cities:** New Delhi, Ludhiana, Chandigarh
- **Start:** 8 Oct 2026, 12:00 UTC (5:30 pm IST), going back 48 hours
- **UrbanWise:** the app's own code (`back_trajectory`), 925 hPa winds from Open-Meteo, hourly steps, nearest point on a 2° grid
- **HYSPLIT:** READY web version, GFS 0.25° meteorology, backward, isobaric, starting 500 m above ground (about the 925 hPa level here)

HYSPLIT has its own trajectory maths, its own handling of the wind data and finer steps, and has nothing to do with our code, so it's a fair independent check.

We measure the distance between the two paths at 6, 12, 24, 36 and 48 hours back. For scale, the app counts a fire as on the path if it's within 24 km of it at 6 h, 51 km at 24 h and 75 km at 48 h.

## Results

_Pending. Filled in once the HYSPLIT runs are done._

| City | Start | 6 h | 12 h | 24 h | 36 h | 48 h | Our trail length |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |

## Reproduce it

1. Run a HYSPLIT back-trajectory on the [READY site](https://www.ready.noaa.gov/HYSPLIT_traj.php) with the settings above and save the "trajectory endpoints" text file as `docs/validation/hysplit_<city>.txt`.
2. From `backend/`:

```bash
venv/bin/python scripts/validate_trajectory.py --name "New Delhi" \
  --lat 28.6139 --lon 77.209 --start 2026-10-08T12 \
  --hysplit ../docs/validation/hysplit_delhi.txt --svg ../docs/validation/delhi.svg
```

It prints the table row and draws both paths.
