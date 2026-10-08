import { describe, expect, it } from 'vitest'
import { fireRadius, trailDetail, trailHeadline } from './smokeTrail'

const base = { hours_traced: 48, trail_km: 590, stagnant: false, fire_count: 0, top_districts: [] }

describe('trailHeadline', () => {
  it('names up to three districts', () => {
    const summary = {
      ...base,
      fire_count: 9,
      top_districts: [{ district: 'Sangrur' }, { district: 'Bathinda' }, { district: 'Patiala' }, { district: 'Mansa' }],
    }
    expect(trailHeadline(summary, 'Delhi')).toBe(
      'The air over Delhi likely passed 9 satellite-detected fires, including some near Sangrur, Bathinda and Patiala, in the last 48 hours.',
    )
  })

  it('says "near" outright only when the named districts cover every fire', () => {
    const summary = {
      ...base, fire_count: 3, other_fires: 0,
      top_districts: [{ district: 'Sangrur', fires: 2 }, { district: 'Mansa', fires: 1 }],
    }
    expect(trailHeadline(summary, 'Delhi')).toBe(
      'The air over Delhi likely passed 3 satellite-detected fires near Sangrur and Mansa in the last 48 hours.',
    )
  })

  it('handles one fire outside mapped districts', () => {
    expect(trailHeadline({ ...base, fire_count: 1 }, 'Lucknow'))
      .toBe('The air over Lucknow likely passed 1 satellite-detected fire in the last 48 hours.')
  })

  it('says so when no fires were passed', () => {
    expect(trailHeadline(base, 'Delhi')).toContain('without passing any detected fires')
  })

  it('explains stagnant air instead of fires', () => {
    const summary = { ...base, stagnant: true }
    expect(trailHeadline(summary, 'Delhi')).toContain('barely moved')
    expect(trailDetail(summary)).toContain('Local sources')
  })
})

describe('fireRadius', () => {
  it('grows with intensity and is capped', () => {
    expect(fireRadius(0)).toBe(4)
    expect(fireRadius(25)).toBeGreaterThan(fireRadius(4))
    expect(fireRadius(10000)).toBe(14)
  })
})
