import { describe, expect, it } from 'vitest'
import { bestWindow, ventilationAdvice } from './ventilation'

// Hourly forecast from `start` for `n` hours, with PM2.5 from `pm`.
function forecast(start, n, pm = () => 100) {
  const [date, hh] = start.split('T')
  const base = new Date(`${date}T00:00:00Z`).getTime() + Number(hh.slice(0, 2)) * 3600e3
  return Array.from({ length: n }, (_, k) => {
    const t = new Date(base + k * 3600e3).toISOString().slice(0, 13) + ':00'
    const value = pm(Number(t.slice(11, 13)), t.slice(0, 10))
    return { time: t, pm25: value, aqi: value * 2, category: 'Test' }
  })
}

describe('bestWindow', () => {
  it('picks the cleanest two consecutive hours left today', () => {
    const f = forecast('2026-10-08T09:00', 30, (h) => (h === 15 || h === 16 ? 40 : 100))
    const w = bestWindow(f, '2026-10-08T09:20')
    expect(w).toMatchObject({ start: '2026-10-08T15:00', endHour: 17, day: 'today', pm25: 40 })
  })

  it('judges the window by its worse hour', () => {
    const f = forecast('2026-10-08T09:00', 30, (h) => ({ 15: 30, 16: 60 }[h] ?? 100))
    const w = bestWindow(f, '2026-10-08T09:00')
    expect(w.pm25).toBe(45)
    expect(w.aqi).toBe(120) // from the 60 µg/m³ hour
  })

  it('ignores night hours even if cleaner', () => {
    const f = forecast('2026-10-08T00:00', 24, (h) => (h < 5 ? 5 : 100))
    expect(Number(bestWindow(f, '2026-10-08T00:00').start.slice(11, 13))).toBeGreaterThanOrEqual(6)
  })

  it('moves to tomorrow late in the evening', () => {
    const f = forecast('2026-10-08T21:00', 30)
    const w = bestWindow(f, '2026-10-08T21:10')
    expect(w.day).toBe('tomorrow')
    expect(w.start.startsWith('2026-10-09')).toBe(true)
  })

  it('returns null with no usable hours', () => {
    expect(bestWindow([], '2026-10-08T10:00')).toBeNull()
  })
})

describe('ventilationAdvice', () => {
  it.each([[150, 'open'], [250, 'brief'], [350, 'closed']])('AQI %s → %s', (aqi, action) => {
    expect(ventilationAdvice(aqi).action).toBe(action)
  })
})
