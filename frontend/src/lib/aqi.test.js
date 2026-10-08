import { describe, expect, it } from 'vitest'
import { aqiCategory, categoryStyle, cityNow, formatDay, formatHour, formatInZone, grapStage, relativeHour } from './aqi'

describe('formatHour', () => {
  it.each([
    ['2026-10-09T00:00', '12 am'],
    ['2026-10-09T07:00', '7 am'],
    ['2026-10-09T12:00', '12 pm'],
    ['2026-10-09T15:00', '3 pm'],
  ])('%s → %s', (input, expected) => {
    expect(formatHour(input)).toBe(expected)
  })
})

describe('formatDay', () => {
  it('uses the local date in the timestamp, not the browser timezone', () => {
    expect(formatDay('2026-10-09T00:00')).toBe('Fri, 9 Oct')
  })
})

describe('categoryStyle', () => {
  it('falls back to grey for unknown categories', () => {
    expect(categoryStyle(undefined).bg).toBe('#8A94A6')
  })
})

describe('cityNow', () => {
  it('gives wall-clock time in the city, whatever the browser timezone', () => {
    const instant = new Date('2026-10-08T09:35:00Z')
    expect(cityNow('Asia/Kolkata', instant)).toBe('2026-10-08T15:05')
    expect(cityNow('UTC', instant)).toBe('2026-10-08T09:35')
  })

  it('returns an empty string for an unknown timezone', () => {
    expect(cityNow('Not/AZone')).toBe('')
  })
})

describe('aqiCategory and grapStage', () => {
  it.each([[0, 'Good'], [50, 'Good'], [51, 'Satisfactory'], [200, 'Moderate'], [201, 'Poor'], [400, 'Very Poor'], [401, 'Severe']])(
    'AQI %s → %s', (aqi, cat) => expect(aqiCategory(aqi)).toBe(cat),
  )
  it.each([[200, null], [201, 'I'], [301, 'II'], [401, 'III'], [451, 'IV']])(
    'GRAP for %s → %s', (aqi, stage) => expect(grapStage(aqi)).toBe(stage),
  )
})

describe('formatInZone', () => {
  it('shows a UTC time in the city timezone', () => {
    expect(formatInZone('2026-10-09T20:00:00+00:00', 'Asia/Kolkata')).toBe('Sat 1 am')
    expect(formatInZone('2026-10-09T08:00:00+00:00', 'Asia/Kolkata')).toBe('Fri 1 pm')
  })

  it('returns an empty string for a missing or invalid time', () => {
    expect(formatInZone(null, 'Asia/Kolkata')).toBe('')
    expect(formatInZone('not a date', 'Asia/Kolkata')).toBe('')
  })
})

describe('relativeHour', () => {
  it('uses the real local date, not the data timestamp', () => {
    // 00:15 on the 9th: 7 am on the 9th is *today*, even if data still says the 8th.
    expect(relativeHour('2026-10-09T07:00', '2026-10-09T00:15')).toBe('7 am')
    expect(relativeHour('2026-10-10T07:00', '2026-10-09T00:15')).toBe('tomorrow 7 am')
    expect(relativeHour(null, '2026-10-09T00:15')).toBe('')
  })
})
