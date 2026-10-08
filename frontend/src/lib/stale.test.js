import { describe, expect, it } from 'vitest'
import { staleNote } from './stale'

describe('staleNote', () => {
  it('is empty when everything is fresh', () => {
    expect(staleNote({}, null, { stale: null })).toBe('')
  })

  it('uses the oldest stale payload', () => {
    expect(staleNote({ stale: { age_min: 20 } }, { stale: { age_min: 130 } }))
      .toBe('A data provider is busy, so some of this is from about 2 h ago.')
  })

  it('says minutes for recent data', () => {
    expect(staleNote({ stale: { age_min: 0 } })).toBe('A data provider is busy, so some of this is from 1 min ago.')
  })
})
