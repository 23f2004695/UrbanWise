import { describe, expect, it } from 'vitest'
import { escapeHtml } from './html'

describe('escapeHtml', () => {
  it('neutralises markup', () => {
    expect(escapeHtml('<img src=x onerror="alert(1)">')).toBe('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;')
  })

  it('leaves normal names (including Indian scripts) readable', () => {
    expect(escapeHtml('New Delhi')).toBe('New Delhi')
    expect(escapeHtml('ਲੁਧਿਆਣਾ')).toBe('ਲੁਧਿਆਣਾ')
    expect(escapeHtml("D'Souza & Sons")).toBe('D&#39;Souza &amp; Sons')
  })

  it('handles missing values and numbers', () => {
    expect(escapeHtml(null)).toBe('')
    expect(escapeHtml(42)).toBe('42')
  })
})
