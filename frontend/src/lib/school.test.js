import { describe, expect, it } from 'vitest'
import { daySummary, decisionStyle, isPast } from './school'

describe('daySummary', () => {
  it('is driven by the strictest slot', () => {
    const slots = [{ decision: 'go' }, { decision: 'limit' }, { decision: 'caution' }]
    expect(daySummary(slots)).toBe('Limit outdoor activities')
  })

  it('ignores slots with no data when others exist', () => {
    expect(daySummary([{ decision: 'unknown' }, { decision: 'go' }]))
      .toBe('All outdoor activities can go ahead')
  })
})

describe('isPast', () => {
  it('compares against the current hour', () => {
    expect(isPast('2026-10-08', '08:00', '2026-10-08T13:30')).toBe(true)
    expect(isPast('2026-10-08', '13:00', '2026-10-08T13:30')).toBe(false)
    expect(isPast('2026-10-09', '08:00', '2026-10-08T13:30')).toBe(false)
  })
})

describe('decisionStyle', () => {
  it('pairs every decision with a symbol, not just a colour', () => {
    for (const d of ['go', 'caution', 'limit', 'cancel', 'unknown']) {
      expect(decisionStyle(d).symbol).toBeTruthy()
    }
  })
})
