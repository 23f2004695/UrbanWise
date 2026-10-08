import { describe, expect, it } from 'vitest'
import {
  cigarettes, exposure, formatCigarettes, formatDuration, savingPercent,
} from './exposure'

describe('cigarettes', () => {
  it('matches the Berkeley Earth rule at rest for a full day', () => {
    expect(cigarettes(22, 24, 'resting')).toBeCloseTo(1)
  })

  it('scales with breathing effort', () => {
    expect(cigarettes(88, 1, 'sports')).toBeCloseTo(3.5 * cigarettes(88, 1, 'resting'))
  })

  it('never goes negative', () => {
    expect(cigarettes(-5, 2, 'walking')).toBe(0)
  })
})

describe('exposure', () => {
  it('rates the same dose as riskier for sensitive people', () => {
    const adult = exposure({ pm25: 150, hours: 1, activity: 'sports', person: 'adult' })
    const asthma = exposure({ pm25: 150, hours: 1, activity: 'sports', person: 'sensitive' })
    // 150 × 1 h × 3.5 / 528 ≈ 0.99 cigarettes for both…
    expect(asthma.cigarettes).toBe(adult.cigarettes)
    // …but weighted ×1 stays under 1 (moderate) while ×2 crosses it (high).
    expect(adult.level).toBe('moderate')
    expect(asthma.level).toBe('high')
  })

  it.each([
    [10, 0.5, 'resting', 'adult', 'low'],
    [100, 1, 'walking', 'adult', 'moderate'],
    [250, 2, 'sports', 'child', 'very-high'],
  ])('pm25 %s for %s h %s (%s) → %s', (pm25, hours, activity, person, level) => {
    expect(exposure({ pm25, hours, activity, person }).level).toBe(level)
  })
})

describe('savingPercent', () => {
  it('reports meaningful savings only', () => {
    expect(savingPercent(100, 60)).toBe(40)
    expect(savingPercent(100, 90)).toBeNull()
    expect(savingPercent(0, 10)).toBeNull()
    expect(savingPercent(100, null)).toBeNull()
  })
})

describe('formatting', () => {
  it('formats cigarettes readably', () => {
    expect(formatCigarettes(0.04)).toBe('less than 0.1')
    expect(formatCigarettes(0.46)).toBe('0.5')
    expect(formatCigarettes(2.0)).toBe('2')
    expect(formatCigarettes(2.34)).toBe('2.3')
    expect(formatCigarettes(12.6)).toBe('13')
  })

  it('formats durations', () => {
    expect(formatDuration(0.25)).toBe('15 min')
    expect(formatDuration(1)).toBe('1 h')
    expect(formatDuration(1.5)).toBe('1 h 30 min')
  })
})
