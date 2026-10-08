import { describe, expect, it } from 'vitest'
import { forecastHeadline, localFiresNote } from './smokeForecast'

const incoming = {
  alert: { incoming: true, first_arrival_h: 34, first_arrival_time: '2026-10-09T20:00:00+00:00', fires: 45, districts: ['Phalodi'] },
  local_fires: 4,
}

describe('forecastHeadline', () => {
  it('gives place, time in the city timezone, and hours', () => {
    expect(forecastHeadline(incoming, 'New Delhi', 'Asia/Kolkata')).toBe(
      'Smoke from 45 satellite-detected fires near Phalodi may reach New Delhi around Sat 1 am — about 34 hours from now (model estimate).',
    )
  })

  it('reassures when nothing is coming', () => {
    expect(forecastHeadline({ alert: { incoming: false }, local_fires: 0 }, 'Jaipur', 'Asia/Kolkata'))
      .toBe("Our model doesn't expect smoke from currently detected fires to reach Jaipur in the next 48 hours.")
  })
})

describe('localFiresNote', () => {
  it('mentions nearby fires only when there are some', () => {
    expect(localFiresNote(incoming)).toContain('4 fires were also detected')
    expect(localFiresNote({ local_fires: 1 })).toContain('1 fire was')
    expect(localFiresNote({ local_fires: 0 })).toBe('')
  })
})
