import { describe, expect, it } from 'vitest'
import { detectLang, pickVoice } from './speech'

describe('detectLang', () => {
  it.each([
    ['Is it safe to run?', 'en-IN'],
    ['क्या मैं दौड़ सकता हूँ?', 'hi-IN'],
    ['ਕੀ ਮੈਂ ਦੌੜ ਸਕਦਾ ਹਾਂ?', 'pa-IN'],
    ['AQI 197 है', 'hi-IN'],
  ])('%s → %s', (text, lang) => {
    expect(detectLang(text)).toBe(lang)
  })
})

describe('pickVoice', () => {
  const mac = [
    { lang: 'en-IN', name: 'Rishi' },
    { lang: 'hi-IN', name: 'Lekha' },
    { lang: 'en-US', name: 'Samantha' },
  ]

  it('uses a matching device voice when there is one', () => {
    expect(pickVoice(mac, 'hi-IN').name).toBe('Lekha')
    expect(pickVoice(mac, 'en-IN').name).toBe('Rishi')
  })

  it('returns null for Punjabi on a typical Mac, so the server voice is used', () => {
    expect(pickVoice(mac, 'pa-IN')).toBeNull()
  })

  it('accepts underscore and base-language variants', () => {
    expect(pickVoice([{ lang: 'pa_IN', name: 'X' }], 'pa-IN').name).toBe('X')
    expect(pickVoice([{ lang: 'pa-Guru-IN', name: 'Y' }], 'pa-IN').name).toBe('Y')
  })
})
