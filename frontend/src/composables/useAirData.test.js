import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAirData } from './useAirData'

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

afterEach(() => vi.unstubAllGlobals())

describe('useLatest (via useAirData)', () => {
  it('drops the previous city when a different one is requested, even if it fails', async () => {
    const delhi = { current: { aqi: 195 } }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => delhi })
      .mockResolvedValueOnce({ ok: false, status: 502, json: async () => ({ error: 'down' }) }))
    const { air, error, load } = useAirData()
    await load({ lat: 28.6, lon: 77.2 })
    expect(air.value).toEqual(delhi)
    const pending = load({ lat: 30.9, lon: 75.8 })
    expect(air.value).toBeNull()                 // never shows Delhi under Ludhiana
    await pending
    expect(air.value).toBeNull()
    expect(error.value).toBe('down')
  })

  it('keeps data while reloading the same place', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ a: 1 }) }))
    const { air, load } = useAirData()
    await load({ lat: 1, lon: 2 })
    const pending = load({ lat: 1, lon: 2 })
    expect(air.value).toEqual({ a: 1 })
    await pending
  })

  it('ignores a slow response for a city the user already left', async () => {
    const slow = deferred()
    vi.stubGlobal('fetch', vi.fn()
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ city: 'B' }) }))
    const { air, load } = useAirData()
    const first = load({ lat: 1, lon: 1 })
    await load({ lat: 2, lon: 2 })
    slow.resolve({ ok: true, json: async () => ({ city: 'A' }) })
    await first
    expect(air.value).toEqual({ city: 'B' })
  })
})
