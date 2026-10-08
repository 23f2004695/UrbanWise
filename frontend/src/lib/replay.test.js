import { describe, expect, it } from 'vitest'
import { isReplayCity, replayInfo } from './replay'

describe('replay helpers', () => {
  it('knows the 8 Oct 2026 snapshot and its cities', () => {
    expect(replayInfo('2026-10-08').cities.map((c) => c.name)).toEqual(['New Delhi', 'Ludhiana', 'Chandigarh'])
    expect(replayInfo('2025-01-01')).toBeNull()
    // Regression: an absent ?replay= must mean "no replay", whatever is active.
    expect(replayInfo(undefined)).toBeNull()
    expect(replayInfo('undefined')).toBeNull()
  })

  it('matches nearby coordinates only', () => {
    expect(isReplayCity({ lat: 28.62, lon: 77.21 }, '2026-10-08')).toBe(true)
    expect(isReplayCity({ lat: 26.92, lon: 75.79 }, '2026-10-08')).toBe(false) // Jaipur
    expect(isReplayCity({ lat: 28.62, lon: 77.21 }, '')).toBe(false)
    expect(isReplayCity({ lat: 28.62, lon: 77.21 }, undefined)).toBe(false)
  })
})
