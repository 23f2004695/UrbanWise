// Speech helpers. Listening uses the browser's speech recognition. Speaking
// uses the device's own voice when it has one for the language (instant,
// free); otherwise — e.g. Punjabi, which most devices lack — the server
// generates the audio.

export const VOICE_LANGS = [
  { id: 'en-IN', label: 'EN' },
  { id: 'hi-IN', label: 'हिं' },
  { id: 'pa-IN', label: 'ਪੰ' },
]

export function getRecognition() {
  const Ctor = typeof window !== 'undefined'
    && (window.SpeechRecognition || window.webkitSpeechRecognition)
  return Ctor ? new Ctor() : null
}

export const canSpeak = () => typeof window !== 'undefined' && ('speechSynthesis' in window || 'Audio' in window)

// Pick a speech language from the script the text is written in.
export function detectLang(text) {
  if (/[਀-੿]/.test(text)) return 'pa-IN'
  if (/[ऀ-ॿ]/.test(text)) return 'hi-IN'
  return 'en-IN'
}

// Voices load asynchronously in some browsers; wait briefly for them.
function loadVoices() {
  if (!('speechSynthesis' in window)) return Promise.resolve([])
  const voices = window.speechSynthesis.getVoices()
  if (voices.length) return Promise.resolve(voices)
  return new Promise((resolve) => {
    const done = () => resolve(window.speechSynthesis.getVoices())
    window.speechSynthesis.addEventListener('voiceschanged', done, { once: true })
    setTimeout(done, 1000)
  })
}

// Best local voice for e.g. "hi-IN": exact match first, then same language.
export function pickVoice(voices, lang) {
  const base = lang.split('-')[0]
  return voices.find((v) => v.lang.replace('_', '-') === lang)
    || voices.find((v) => v.lang.toLowerCase().startsWith(`${base}-`) || v.lang === base)
    || null
}

// Only one thing speaks at a time. Every speak()/stopSpeaking() bumps the
// generation; anything started by an older generation stops itself.
let generation = 0
let currentAudio = null
let pendingFetch = null   // AbortController for an in-flight /api/speak
let settlePending = null  // resolves the promise of whatever is playing

export function stopSpeaking() {
  generation++
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  pendingFetch?.abort()
  pendingFetch = null
  if (currentAudio) {
    currentAudio.pause()
    URL.revokeObjectURL(currentAudio.src)
    currentAudio = null
  }
  settlePending?.()
  settlePending = null
}

/**
 * Speak `text`. Resolves when playback finishes or is stopped (by the user, or
 * because something else started speaking). `onStart(source)` fires once audio
 * begins: source is 'device' or 'server'.
 */
export async function speak(text, { onStart = () => {} } = {}) {
  stopSpeaking()
  const mine = generation
  const lang = detectLang(text)
  const clean = text.replace(/•/g, '')
  const voice = pickVoice(await loadVoices(), lang)
  if (mine !== generation) return

  if (voice) {
    return new Promise((resolve) => {
      settlePending = resolve
      const u = new SpeechSynthesisUtterance(clean)
      u.lang = voice.lang
      u.voice = voice
      u.onstart = () => onStart('device')
      u.onend = resolve
      u.onerror = resolve
      window.speechSynthesis.speak(u)
    })
  }

  const controller = new AbortController()
  pendingFetch = controller
  let blob
  try {
    const res = await fetch('/api/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: clean }),
      signal: controller.signal,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.error || 'Speech is unavailable right now.')
    }
    blob = await res.blob()
  } catch (err) {
    if (err.name === 'AbortError' || mine !== generation) return // stopped while loading
    throw err
  } finally {
    if (pendingFetch === controller) pendingFetch = null
  }
  if (mine !== generation) return

  const audio = new Audio(URL.createObjectURL(blob))
  currentAudio = audio
  return new Promise((resolve, reject) => {
    settlePending = resolve
    const finish = (err) => {
      // Only clean up if this clip is still the current one.
      if (currentAudio === audio) {
        URL.revokeObjectURL(audio.src)
        currentAudio = null
        settlePending = null
      }
      err ? reject(err) : resolve()
    }
    audio.onplaying = () => onStart('server')
    audio.onended = () => finish()
    audio.onerror = () => finish(new Error('Could not play the audio.'))
    audio.play().catch((err) => finish(err))
  })
}
