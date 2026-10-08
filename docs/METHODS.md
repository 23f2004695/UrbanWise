# How UrbanWise works

What each number in the app is based on, what we assume, and where it can be wrong.
Everything here is in the code under `backend/services/` and `frontend/src/lib/`.

UrbanWise is a planning aid. None of it is a measurement or medical advice.

## Air quality and AQI

**Data.** PM2.5 and PM10 come from the CAMS global model (ECMWF / Copernicus) through the Open-Meteo Air Quality API. These are model estimates on a grid of roughly 40 km, not readings from a CPCB station.

**AQI.** We use the CPCB National AQI breakpoints for PM2.5 and PM10. The "now" AQI uses the average of the last 24 hours, as CPCB does for particulate matter. The higher of the two sub-indices is the AQI. CPCB doesn't define values above AQI 500, so we cap Severe at PM2.5 380 and PM10 600 µg/m³, which is the usual convention.

**Forecast.** The 48-hour chart is hourly. Each bar is the AQI from that single hour's concentration, so it moves faster than the 24-hour AQI and is meant for picking better or worse hours, not for comparing with the official daily number.

**Limits.**
- A model grid cell can't see a local source like a busy road or a garbage fire next to a school.
- CAMS can be off by a lot on individual days, especially during fire season.
- We only use PM2.5 and PM10. CPCB's AQI can also be set by NO2, O3, CO, SO2 or NH3, so the official AQI can be higher than ours.

## GRAP stage

GRAP is the Delhi-NCR action plan from CAQM. We map the day-average AQI to the stages (201–300 Stage I, 301–400 II, 401–450 III, above 450 IV). We only show it for places within 130 km of Delhi, which is a rough stand-in for the real NCR boundary. The official stage is declared by CAQM and can differ from ours.

## School Mode

For each activity (assembly, PE, dismissal) we look up the forecast AQI for that hour and apply:

| AQI | Guidance |
| :--- | :--- |
| up to 100 | Go |
| 101–200 | Go with care (children with asthma avoid heavy exertion) |
| 201–300 | Limit (PE indoors, short assembly) |
| 301–400 | Cancel outdoor activities |
| above 400 | Cancel, indoor only |

These are our own rules built on the CPCB health categories. They are not an official CPCB or school board rule. Times round down to the hour because the forecast is hourly.

## Smoke Trail (where the air came from)

**Data.** Winds at 925 hPa (about 750 m up) from the Open-Meteo forecast API, on a 7 × 7 grid with points 2° apart around the city. Fire detections from NASA FIRMS (VIIRS on Suomi NPP, last 48 hours), dropping low-confidence ones.

**Method.** A simple back-trajectory: start at the city at the current hour and step back one hour at a time against the wind at that place and time, for up to 48 hours. Then we count fires that are close to the path at roughly the time the air passed them:
- close means within 15 km at the start, growing by 1.5 km per hour back, up to 75 km
- roughly the time means within 12 hours, since the satellite only passes about twice a day

Fires are named by the nearest district (from a list of 92 in North India and Pakistan Punjab) if one is within 60 km.

**Limits.**
- One height only. Real smoke is spread through the lowest few km and the wind changes with height.
- Each step uses the nearest grid point's wind, and the grid is coarse (about 200 km). Turning winds between points are missed.
- The trace stops if it leaves the wind grid (about 650 km from the city), so very fast winds give a shorter trail.
- No vertical motion, rain washout, chemistry or mixing.
- A fire on the path doesn't mean its smoke reached the city or how much. That's why we say "likely passed", not "caused".
- Fires under cloud, small fires and fires between satellite passes are missed by VIIRS.

## Incoming Smoke Alert (what may arrive)

The same engine run forwards. We group fires from the last 36 hours into cells of 0.5° and keep the 8 with the most fire radiative power. From the centre of each group we run a 48-hour forward trajectory on forecast winds. If the path comes within the same growing distance of the city, the time it first does so is the arrival time. Fires within 30 km of the city count as local, not incoming.

**Second weather model.** We run the same thing on GFS winds as well. If both bring smoke, the app says the two models agree and shows when GFS has it arriving. If only one does, it says they disagree. If GFS can't be fetched, the alert is shown without this check.

**Assumptions and limits.**
- It assumes the fires keep burning. Most crop fires burn for hours, not days, so a single burst may not last long enough to arrive.
- Forecast winds get less reliable further ahead. An arrival 40 hours out is much less certain than one 10 hours out.
- It says when smoke may arrive, not how much, so it doesn't predict the AQI change.
- All the Smoke Trail limits above apply too.

## Smoke Radar

An animation for showing the idea, not a forecast product. Particles are released from each detected fire and moved by the same 925 hPa winds (interpolated in space and time in the browser), fading out after 30 hours. The coloured city dots are the CAMS hourly AQI. The wind streaks are sped up so you can see them.

## Exposure calculator

Uses the Berkeley Earth rule of thumb that breathing 22 µg/m³ of PM2.5 for 24 hours is about the same as smoking one cigarette. Walking counts as 2× the air breathed at rest, and sport as 3.5×. Children and people with asthma, heart conditions or old age get a higher weight for the advice band (1.5× and 2×), not for the cigarette number. It's a way to make the number feel real, not a dose estimate.

## Ventilation window

The two consecutive hours between 6 am and 10 pm with the lowest forecast PM2.5, today if there's still time, otherwise tomorrow. It's judged by the worse of the two hours. It's based on outdoor air, so it ignores cooking, incense and other indoor sources.

## Parent notices and the assistant

Every number, decision and time comes from the code above. Gemini only writes the wording.
- For notices, the facts are passed in and the wording is checked. If Gemini fails or returns the wrong script for Hindi or Punjabi, we fall back to an English template.
- The assistant gets the city's data as its only facts and is told to say "estimate" and "may", and to mention GRAP only for Delhi-NCR.

Text from a language model can still be wrong, so the principal should review a notice before sending it.

## Validation

We compared our trajectories with NOAA HYSPLIT for Delhi, Ludhiana and Chandigarh. Short version: on the same winds our path stays close for the first few hours but drifts after that, mostly because of the coarse 2° wind grid, and two different weather models can send the air in very different directions. The smoke alert agreed across three weather models; the Smoke Trail's named fires did not. Details in [VALIDATION.md](VALIDATION.md).
