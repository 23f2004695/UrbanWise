<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { VOICE_LANGS, canSpeak, getRecognition, speak, stopSpeaking } from '../lib/speech'
import Icon3D from './Icon3D.vue'
import { replayDate } from '../lib/replay'

const props = defineProps({
  place: { type: Object, required: true },
  times: { type: Object, default: () => ({}) },
})

const MAX_CHARS = 500
const SUGGESTIONS = [
  'Can we hold sports day tomorrow?',
  'Is it safe to go for a run now?',
  'Where is the smoke coming from?',
  'When should I open my windows today?',
]

const messages = ref([]) // { role: 'user' | 'assistant', text, fallback? }
const draft = ref('')
const loading = ref(false)
const list = ref(null)
const voiceLang = ref('en-IN')
const listening = ref(false)
const voiceSupported = !!getRecognition()
const speechSupported = canSpeak()
let recognition = null

// Read-aloud state for one message at a time: 'loading' | 'playing'.
const speaking = ref({ index: -1, state: '' })
const speakError = ref('')

async function toggleSpeak(i, text) {
  if (speaking.value.index === i) {
    stopSpeaking()
    speaking.value = { index: -1, state: '' }
    return
  }
  speakError.value = ''
  speaking.value = { index: i, state: 'loading' }
  try {
    await speak(text, { onStart: () => { if (speaking.value.index === i) speaking.value.state = 'playing' } })
  } catch (err) {
    speakError.value = err.message
  } finally {
    if (speaking.value.index === i) speaking.value = { index: -1, state: '' }
  }
}

// Each conversation has an id; replies for an older one are dropped.
let conversation = 0

// A new city means new data; start a fresh conversation.
watch(() => props.place, () => {
  conversation++
  loading.value = false
  stopSpeaking()
  speaking.value = { index: -1, state: '' }
  messages.value = []
  draft.value = ''
})

async function scrollToEnd() {
  await nextTick()
  list.value?.scrollTo({ top: list.value.scrollHeight, behavior: 'smooth' })
}

async function send(text = draft.value) {
  const message = text.trim()
  if (!message || loading.value) return
  const mine = conversation
  const history = messages.value
    .filter((m) => !m.fallback)
    .map(({ role, text: t }) => ({ role, text: t }))
  messages.value.push({ role: 'user', text: message })
  draft.value = ''
  loading.value = true
  scrollToEnd()
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat: props.place.lat,
        lon: props.place.lon,
        place_name: props.place.name,
        message,
        history,
        times: props.times,
        replay: replayDate.value || undefined,
      }),
    })
    const body = await res.json().catch(() => ({}))
    if (mine !== conversation) return // the user switched city meanwhile
    if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`)
    messages.value.push({ role: 'assistant', text: body.reply, fallback: body.fallback })
  } catch (err) {
    if (mine !== conversation) return
    messages.value.push({ role: 'assistant', text: `Sorry, something went wrong: ${err.message}`, fallback: true })
  } finally {
    if (mine === conversation) {
      loading.value = false
      scrollToEnd()
    }
  }
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function toggleVoice() {
  if (listening.value) {
    recognition?.stop()
    return
  }
  recognition = getRecognition()
  if (!recognition) return
  recognition.lang = voiceLang.value
  recognition.interimResults = true
  recognition.onresult = (event) => {
    const result = event.results[event.results.length - 1]
    draft.value = result[0].transcript
    if (result.isFinal) send(result[0].transcript)
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
  listening.value = true
  recognition.start()
}

onBeforeUnmount(() => { recognition?.abort(); stopSpeaking() })
</script>

<template>
  <section class="card assistant" aria-labelledby="assistant-title">
    <div class="card-head">
      <Icon3D name="speech_balloon" :size="46" :delay="2.6" />
      <div>
        <h2 id="assistant-title">Ask UrbanWise</h2>
        <p class="muted small">Type or speak in English, हिंदी or ਪੰਜਾਬੀ</p>
      </div>
    </div>

    <div ref="list" class="messages" aria-live="polite">
      <div v-if="!messages.length" class="suggestions">
        <button v-for="s in SUGGESTIONS" :key="s" type="button" @click="send(s)">{{ s }}</button>
      </div>

      <div
        v-for="(m, i) in messages"
        :key="i"
        class="msg"
        :class="[m.role, { fallback: m.fallback }]"
      >
        <p>{{ m.text }}</p>
        <button
          v-if="m.role === 'assistant' && speechSupported && !m.fallback"
          type="button"
          class="speak"
          :class="speaking.index === i ? speaking.state : ''"
          :aria-label="speaking.index === i ? 'Stop reading' : 'Read this answer aloud'"
          :title="speaking.index === i && speaking.state === 'loading' ? 'Preparing audio…' : ''"
          @click="toggleSpeak(i, m.text)"
        >{{ speaking.index !== i ? '🔊' : speaking.state === 'loading' ? '⏳' : '⏹' }}</button>
      </div>

      <div v-if="loading" class="msg assistant thinking" role="status">Checking the data…</div>
      <p v-if="speakError" class="speak-error small" role="alert">{{ speakError }}</p>
    </div>

    <form class="composer" @submit.prevent="send()">
      <label for="assistant-input" class="visually-hidden">Your question</label>
      <textarea
        id="assistant-input"
        v-model="draft"
        rows="1"
        :maxlength="MAX_CHARS"
        :placeholder="listening ? 'Listening…' : 'Ask about the air…'"
        @keydown="onKey"
      ></textarea>

      <template v-if="voiceSupported">
        <label for="voice-lang" class="visually-hidden">Voice language</label>
        <select id="voice-lang" v-model="voiceLang" :disabled="listening">
          <option v-for="l in VOICE_LANGS" :key="l.id" :value="l.id">{{ l.label }}</option>
        </select>
        <button
          type="button"
          class="mic"
          :class="{ on: listening }"
          :aria-pressed="listening"
          :aria-label="listening ? 'Stop listening' : 'Ask by voice'"
          @click="toggleVoice"
        >🎙</button>
      </template>

      <button type="submit" class="send" :disabled="loading || !draft.trim()">Send</button>
    </form>
    <p class="muted small note">Answers use {{ place.name }}'s data only · not medical advice</p>
  </section>
</template>

<style scoped>
.assistant { display: flex; flex-direction: column; }

.assistant > p { margin: 0; }

.messages {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 220px;
  max-height: 380px;
  overflow-y: auto;
  margin: 12px 0;
  padding: 4px 2px;
}

.suggestions { display: flex; flex-wrap: wrap; gap: 6px; margin: auto 0 0; }

.suggestions button {
  padding: 7px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  cursor: pointer;
  font-size: 0.9rem;
  text-align: left;
}

.msg {
  position: relative;
  max-width: 88%;
  padding: 9px 12px;
  border-radius: 14px;
  line-height: 1.5;
}

.msg p { margin: 0; white-space: pre-wrap; }

.msg.user {
  align-self: flex-end;
  background: var(--brand);
  color: var(--surface);
  border-bottom-right-radius: 4px;
}

.msg.assistant {
  align-self: flex-start;
  background: var(--surface-2);
  border-bottom-left-radius: 4px;
  padding-right: 36px;
}

.msg.fallback { color: var(--muted); font-style: italic; }

.thinking { color: var(--muted); }

.speak.loading { animation: pulse 1s ease-in-out infinite; }

@keyframes pulse { 50% { opacity: 0.35; } }

.speak-error { margin: 0; color: #B42318; }

.speak {
  position: absolute;
  top: 6px;
  right: 6px;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 0.95rem;
}

.composer { display: flex; gap: 6px; align-items: flex-end; }

.composer textarea {
  flex: 1;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  resize: none;
  font: inherit;
}

.composer select, .composer button {
  height: 40px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  cursor: pointer;
}

.composer select { padding: 0 6px; }

.mic { width: 40px; }

.mic.on { background: #E5484D; border-color: #E5484D; }

.send {
  padding: 0 14px;
  background: var(--brand) !important;
  border-color: var(--brand) !important;
  color: var(--surface);
  font-weight: 600;
}

.send:disabled { opacity: 0.5; cursor: default; }

.note { margin-top: 8px !important; }

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
