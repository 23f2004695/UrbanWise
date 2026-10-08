// Smoke Radar maths: wind interpolation and particle movement.
// radar = { grid: { lats, lons }, u: [frame][lat*nLon + lon], v: same }  (km/h, east/north)

const KM_PER_DEG = 111

/** Wind [east, north] in km/h at a position and fractional frame, or null outside the grid. */
export function windAt(radar, lat, lon, frame) {
  const { lats, lons } = radar.grid
  const nLon = lons.length
  const fi = (lat - lats[0]) / (lats[1] - lats[0])
  const fj = (lon - lons[0]) / (lons[1] - lons[0])
  if (fi < 0 || fj < 0 || fi > lats.length - 1 || fj > nLon - 1) return null
  const last = radar.u.length - 1
  const f = Math.max(0, Math.min(frame, last))
  const f0 = Math.floor(f)
  const f1 = Math.min(f0 + 1, last)
  const tf = f - f0

  const i0 = Math.min(Math.floor(fi), lats.length - 2)
  const j0 = Math.min(Math.floor(fj), nLon - 2)
  const di = fi - i0
  const dj = fj - j0

  const sample = (field, k) => {
    const a = field[k][i0 * nLon + j0]
    const b = field[k][i0 * nLon + j0 + 1]
    const c = field[k][(i0 + 1) * nLon + j0]
    const d = field[k][(i0 + 1) * nLon + j0 + 1]
    if (a == null || b == null || c == null || d == null) return null
    return (a * (1 - dj) + b * dj) * (1 - di) + (c * (1 - dj) + d * dj) * di
  }
  const lerp = (field) => {
    const x0 = sample(field, f0)
    const x1 = sample(field, f1)
    if (x0 == null || x1 == null) return null
    return x0 * (1 - tf) + x1 * tf
  }
  const u = lerp(radar.u)
  const v = lerp(radar.v)
  return u == null || v == null ? null : [u, v]
}

/** Move a point by wind [east, north] km/h for `hours`. */
export function advect(lat, lon, [u, v], hours) {
  const nLat = lat + (v * hours) / KM_PER_DEG
  const nLon = lon + (u * hours) / (KM_PER_DEG * Math.cos((lat * Math.PI) / 180))
  return [nLat, nLon]
}

export function gridBounds(radar) {
  const { lats, lons } = radar.grid
  return [[lats[0], lons[0]], [lats.at(-1), lons.at(-1)]]
}
