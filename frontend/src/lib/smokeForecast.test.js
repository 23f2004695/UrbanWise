import { describe, expect, it } from 'vitest'
import { forecastHeadline, localFiresNote, modelsCheck } from './smokeForecast'

const incoming = {
  alert: { incoming: true, first_arrival_h: 34, first_arrival_time: '2026-10-09T20:00:00+00:00', fires: 45, districts: ['Phalodi'] },
  local_fires: 4,
}

describe('forecastHeadline', () => {
  it('gives place, time in the city timezone, and hours', () => {
    expect(forecastHeadline(incoming, 'New Delhi', 'Asia/Kolkata')).toBe(
      'Smoke from 45 fires near Phalodi may reach New Delhi around Sat 1 am (in about 34 h).',
    )
  })

  it('reassures when nothing is coming', () => {
    expect(forecastHeadline({ alert: { incoming: false }, local_fires: 0 }, 'Jaipur', 'Asia/Kolkata'))
      .toBe('No smoke from current fires is expected to reach Jaipur in the next 48 hours.')
  })
})

describe('localFiresNote', () => {
  it('mentions nearby fires only when there are some', () => {
    expect(localFiresNote(incoming)).toContain('4 fires were also detected')
    expect(localFiresNote({ local_fires: 1 })).toContain('1 fire was')
    expect(localFiresNote({ local_fires: 0 })).toBe('')
  })
})

describe('modelsCheck', () => {
  const withModels = (incoming, models) => ({ alert: { incoming, models } })

  it('says nothing when there was no second model', () => {
    expect(modelsCheck({ alert: { incoming: true } })).toBeNull()
    expect(modelsCheck(withModels(true, { checked: 1, agree: null }))).toBeNull()
  })

  it("gives the second model's arrival time when both bring smoke", () => {
    const data = { alert: { incoming: true, first_arrival_h: 30, models: { agree: true, second: { first_arrival_h: 21 } } } }
    const check = modelsCheck(data)
    expect(check.chip).toBe('2 models agree')
    expect(check.sentence).toBe('A second weather model (GFS) also brings this smoke, in about 21 h.')
    data.alert.models.second.first_arrival_h = 30
    expect(modelsCheck(data).sentence).toContain('at about the same time')
  })

  it('agreeing on no smoke is short', () => {
    expect(modelsCheck(withModels(false, { agree: true, second: { incoming: false } })).sentence)
      .toBe('A second weather model (GFS) agrees.')
  })

  it('flags an alert the second model does not back up', () => {
    const check = modelsCheck(withModels(true, { agree: false, second: { incoming: false } }))
    expect(check.chip).toBe('Models disagree')
    expect(check.sentence).toContain('treat it as uncertain')
  })

  it('mentions smoke that only the second model brings', () => {
    const second = { incoming: true, first_arrival_h: 21, fires: 27, districts: ['Phalodi'] }
    expect(modelsCheck(withModels(false, { agree: false, second })).sentence).toBe(
      'A second weather model (GFS) shows smoke from 27 fires near Phalodi may arrive in about 21 h, so keep an eye on it.',
    )
  })
})
