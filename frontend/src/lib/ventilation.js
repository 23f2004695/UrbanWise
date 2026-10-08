export const WINDOW_HOURS = 2
const FIRST_HOUR = 6   // earliest sensible time to open windows
const LAST_HOUR = 22   // window must end by 10 pm

const hourOf = (iso) => Number(iso.slice(11, 13))

/**
 * Cleanest WINDOW_HOURS consecutive waking hours, today if enough remain,
 * otherwise tomorrow.
 *
 * forecast: [{ time: 'YYYY-MM-DDTHH:00', pm25, aqi, category }] from the current hour
 * nowIso:   city-local 'YYYY-MM-DDTHH:MM'
 */
export function bestWindow(forecast, nowIso) {
  if (!nowIso) return null
  const today = nowIso.slice(0, 10)
  const nowHour = `${nowIso.slice(0, 13)}:00`
  const waking = (f) => hourOf(f.time) >= FIRST_HOUR && hourOf(f.time) + WINDOW_HOURS <= LAST_HOUR
  // Never suggest a window that has already started.
  const upcoming = forecast.filter((f) => f.time >= nowHour)

  const days = [...new Set(upcoming.map((f) => f.time.slice(0, 10)))]
  for (const day of days) {
    const best = cleanestRun(upcoming.filter((f) => f.time.startsWith(day)), waking)
    if (best) return { ...best, day: day === today ? 'today' : 'tomorrow' }
  }
  return null
}

function cleanestRun(hours, startsOk) {
  let best = null
  for (let i = 0; i + WINDOW_HOURS <= hours.length; i++) {
    const run = hours.slice(i, i + WINDOW_HOURS)
    // Hours must be consecutive (the forecast can have gaps).
    if (hourOf(run.at(-1).time) - hourOf(run[0].time) !== WINDOW_HOURS - 1) continue
    if (!startsOk(run[0])) continue
    const pm25 = run.reduce((s, f) => s + f.pm25, 0) / run.length
    // Judge the window by its worse hour so the advice is never too optimistic.
    const worst = run.reduce((a, b) => (b.aqi > a.aqi ? b : a))
    if (!best || pm25 < best.pm25) {
      best = {
        start: run[0].time,
        endHour: hourOf(run.at(-1).time) + 1,
        pm25,
        aqi: worst.aqi,
        category: worst.category,
      }
    }
  }
  return best
}

// What to actually do, based on how clean the best window is.
export function ventilationAdvice(aqi) {
  if (aqi <= 200) {
    return { action: 'open', title: 'Open windows wide',
      text: 'Air out your home or classroom for the full window, ideally with a cross-breeze.' }
  }
  if (aqi <= 300) {
    return { action: 'brief', title: 'Open briefly',
      text: 'Open windows for just 10–15 minutes to refresh stale air, then close them again.' }
  }
  return { action: 'closed', title: 'Keep windows closed',
    text: 'Even the cleanest hour is very polluted. Keep windows shut and run an air purifier if you have one.' }
}
