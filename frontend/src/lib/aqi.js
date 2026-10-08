// Official CPCB colours, with a text colour that meets WCAG AA (≥4.5:1) on each.
export const CATEGORY_STYLES = {
  Good: { bg: '#00B050', fg: '#0B2914' },
  Satisfactory: { bg: '#92D050', fg: '#1A2B10' },
  Moderate: { bg: '#FFD60A', fg: '#2B2300' },
  Poor: { bg: '#FF9900', fg: '#2B1700' },
  'Very Poor': { bg: '#FF0000', fg: '#1A0000' },
  Severe: { bg: '#C00000', fg: '#FFFFFF' },
}

export function categoryStyle(category) {
  return CATEGORY_STYLES[category] || { bg: '#8A94A6', fg: '#17213A' }
}

export const POLLUTANT_NAMES = { pm25: 'PM2.5', pm10: 'PM10' }

// "2026-10-09T15:00" → "3 pm" (times are already in the city's local zone).
export function formatHour(isoLocal) {
  const hour = Number(isoLocal.slice(11, 13))
  if (hour === 0) return '12 am'
  if (hour === 12) return '12 pm'
  return hour < 12 ? `${hour} am` : `${hour - 12} pm`
}

// "2026-10-09T15:00" → "Thu 9 Oct" without timezone shifts.
export function formatDay(isoLocal) {
  const [y, m, d] = isoLocal.slice(0, 10).split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC',
  })
}

// Current wall-clock time in a city's timezone as "YYYY-MM-DDTHH:MM".
// (The data's own timestamp can lag real time by up to an hour.)
export function cityNow(timeZone, date = new Date()) {
  try {
    // The sv-SE locale formats as "2026-10-08 15:05".
    return new Intl.DateTimeFormat('sv-SE', {
      timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).format(date).replace(' ', 'T')
  } catch {
    return ''
  }
}

// Graded Response Action Plan stage for an AQI (null below Stage I).
export function grapStage(aqi) {
  if (aqi == null) return null
  if (aqi > 450) return 'IV'
  if (aqi > 400) return 'III'
  if (aqi > 300) return 'II'
  if (aqi > 200) return 'I'
  return null
}

// CPCB category for an AQI value (client-side mirror of the backend bands).
export function aqiCategory(aqi) {
  if (aqi <= 50) return 'Good'
  if (aqi <= 100) return 'Satisfactory'
  if (aqi <= 200) return 'Moderate'
  if (aqi <= 300) return 'Poor'
  if (aqi <= 400) return 'Very Poor'
  return 'Severe'
}

// A UTC ISO time shown in the city's timezone, e.g. "Sat 1 am".
export function formatInZone(iso, timeZone) {
  // new Date(null) is 1970 — never show a confident wrong time.
  if (!iso || Number.isNaN(new Date(iso).getTime())) return ''
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone, weekday: 'short', hour: 'numeric', hour12: true,
    }).format(new Date(iso)).replace(/\s?([ap])m$/i, (m, x) => ` ${x.toLowerCase()}m`)
  } catch {
    return ''
  }
}

// "3 pm" if `time` is on the same local date as `now`, otherwise "tomorrow 3 pm".
// `now` should be the real city time (cityNow), not a data timestamp.
export function relativeHour(time, now) {
  if (!time) return ''
  return now && time.slice(0, 10) !== now.slice(0, 10) ? `tomorrow ${formatHour(time)}` : formatHour(time)
}
