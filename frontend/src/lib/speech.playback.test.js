import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Fake browser bits: no device voices (like Punjabi on a Mac), a slow server,
// and an Audio element we can inspect.
let audios
let fetches

class FakeAudio {
  constructor(src) { this.src = src; this.paused = true; audios.push(this) }
  play() { this.paused = false; queueMicrotask(() => this.onplaying?.()); return Promise.resolve() }
  pause() { this.paused = true }
  end() { this.paused = true; this.onended?.() }
}

function slowFetch() {
  let respond
  const p = new Promise((resolve, reject) => {
    respond = () => resolve({ ok: true, blob: async () => new Blob(['wav']) })
    fetches.at(-1).signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })))
  })
  return { p, respond }
}

let pending
beforeEach(() => {
  audios = []
  fetches = []
  pending = []
  vi.stubGlobal('window', { speechSynthesis: { getVoices: () => [], cancel() {}, addEventListener() {} } })
  vi.stubGlobal('Audio', FakeAudio)
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:${audios.length}`)
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.stubGlobal('fetch', vi.fn((url, opts) => {
    fetches.push(opts)
    const f = slowFetch()
    pending.push(f)
    return f.p
  }))
  vi.useFakeTimers()
})

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.resetModules() })

async function load() {
  return import('./speech.js')
}

const tick = async () => { await vi.advanceTimersByTimeAsync(1100); await Promise.resolve() }

describe('server speech playback', () => {
  it('starting a second answer cancels the first, so they never overlap', async () => {
    const { speak } = await load()
    const a = speak('ਪਹਿਲਾ ਜਵਾਬ')
    await tick()
    const b = speak('ਦੂਜਾ ਜਵਾਬ')
    await tick()
    pending[1].respond()
    await vi.waitFor(() => expect(audios).toHaveLength(1))
    await expect(a).resolves.toBeUndefined()       // first settled without playing
    expect(fetches[0].signal.aborted).toBe(true)  // its download was cancelled
    expect(audios[0].paused).toBe(false)           // only the second plays
    audios[0].end()
    await b
  })

  it('stop while loading means nothing plays afterwards', async () => {
    const { speak, stopSpeaking } = await load()
    const a = speak('ਜਵਾਬ')
    await tick()
    stopSpeaking()
    await expect(a).resolves.toBeUndefined()
    expect(audios).toHaveLength(0)
  })

  it('stop while playing settles the promise and pauses the audio', async () => {
    const { speak, stopSpeaking } = await load()
    const a = speak('ਜਵਾਬ')
    await tick()
    pending[0].respond()
    await vi.waitFor(() => expect(audios).toHaveLength(1))
    await Promise.resolve()
    stopSpeaking()
    await expect(a).resolves.toBeUndefined()
    expect(audios[0].paused).toBe(true)
  })
})
