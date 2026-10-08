import { describe, expect, it } from 'vitest'
import { advect, windAt } from './radar'

// 3×3 grid, 2 frames. Frame 0: wind east 10; frame 1: wind east 20.
// Second frame has a gap (null) in one corner.
const radar = {
  grid: { lats: [26, 28, 30], lons: [74, 76, 78] },
  u: [Array(9).fill(10), [20, 20, 20, 20, 20, 20, 20, 20, null]],
  v: [Array(9).fill(0), Array(9).fill(0)],
}

describe('windAt', () => {
  it('returns grid values at grid points', () => {
    expect(windAt(radar, 26, 74, 0)).toEqual([10, 0])
  })

  it('interpolates in time between frames', () => {
    expect(windAt(radar, 26, 74, 0.5)).toEqual([15, 0])
  })

  it('interpolates in space', () => {
    const r = { ...radar, u: [[0, 10, 20, 0, 10, 20, 0, 10, 20]], v: [Array(9).fill(0)] }
    expect(windAt(r, 27, 75, 0)[0]).toBeCloseTo(5)
  })

  it('is null outside the grid or where data is missing', () => {
    expect(windAt(radar, 25, 74, 0)).toBeNull()
    expect(windAt(radar, 29.5, 77.5, 1)).toBeNull()
  })

  it('clamps frames to the available range', () => {
    expect(windAt(radar, 26, 74, 99)).toEqual([20, 0])
  })
})

describe('advect', () => {
  it('moves north by speed × time', () => {
    const [lat, lon] = advect(28, 77, [0, 111], 1)
    expect(lat).toBeCloseTo(29)
    expect(lon).toBeCloseTo(77)
  })

  it('accounts for narrower longitude degrees away from the equator', () => {
    const [, lon] = advect(60, 77, [111, 0], 1)
    expect(lon).toBeCloseTo(79) // cos(60°) = 0.5 → twice the degrees
  })
})
