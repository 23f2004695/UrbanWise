<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { formatDay } from '../lib/aqi'
import Icon3D from './Icon3D.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  place: { type: Object, required: true },
  date: { type: String, default: '' },
  times: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['close'])

const LANGS = [
  { id: 'en', label: 'English', lang: 'en' },
  { id: 'hi', label: 'हिंदी', lang: 'hi' },
  { id: 'pa', label: 'ਪੰਜਾਬੀ', lang: 'pa' },
]
const STORAGE_KEY = 'urbanwise.schoolName'

const dialog = ref(null)
const schoolName = ref(readSchoolName())
const loading = ref(false)
const error = ref('')
const result = ref(null)
const texts = ref({ en: '', hi: '', pa: '' }) // editable copies
const lang = ref('en')
const copied = ref(false)

function readSchoolName() {
  try { return localStorage.getItem(STORAGE_KEY) || '' } catch { return '' }
}

function saveSchoolName(name) {
  try { localStorage.setItem(STORAGE_KEY, name) } catch { /* private mode etc. */ }
}

// Bumped whenever the dialog opens or closes, so a notice requested earlier
// (e.g. for another date) can't appear in a newer dialog.
let request = 0

watch(() => props.open, async (open) => {
  request++
  loading.value = false
  await nextTick()
  if (open && !dialog.value.open) {
    result.value = null
    error.value = ''
    lang.value = 'en'
    dialog.value.showModal()
  } else if (!open && dialog.value.open) {
    dialog.value.close()
  }
})

async function generate() {
  const mine = ++request
  loading.value = true
  error.value = ''
  copied.value = false
  saveSchoolName(schoolName.value.trim())
  try {
    const res = await fetch('/api/circular', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        lat: props.place.lat,
        lon: props.place.lon,
        date: props.date,
        school_name: schoolName.value.trim(),
        times: props.times,
      }),
    })
    const body = await res.json().catch(() => ({}))
    if (mine !== request) return
    if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`)
    result.value = body
    texts.value = { en: body.en || '', hi: body.hi || '', pa: body.pa || '' }
    lang.value = 'en'
  } catch (err) {
    if (mine === request) error.value = err.message
  } finally {
    if (mine === request) loading.value = false
  }
}

const current = computed(() => texts.value[lang.value])
const whatsappUrl = computed(() => `https://wa.me/?text=${encodeURIComponent(current.value)}`)

async function copy() {
  try {
    await navigator.clipboard.writeText(current.value)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch {
    error.value = 'Copy failed. Select the text and copy it manually.'
  }
}
</script>

<template>
  <dialog ref="dialog" class="dialog" aria-labelledby="circular-title" @close="emit('close')">
    <div class="head">
      <div class="card-head">
        <Icon3D name="envelope_with_arrow" :size="40" />
        <h2 id="circular-title">Notice to parents · {{ date ? formatDay(`${date}T00:00`) : '' }}</h2>
      </div>
      <button type="button" class="icon" aria-label="Close" @click="emit('close')">✕</button>
    </div>

    <form class="setup" @submit.prevent="generate">
      <label for="school-name">School name</label>
      <div class="row">
        <input
          id="school-name"
          v-model="schoolName"
          type="text"
          maxlength="80"
          placeholder="e.g. Green Valley Public School"
          autocomplete="organization"
        />
        <button type="submit" class="primary" :disabled="loading">
          {{ result ? 'Write again' : 'Write notice' }}
        </button>
      </div>
      <p class="muted small">
        Uses School Mode's forecast for {{ place.name }}. Written in English, Hindi and Punjabi.
      </p>
    </form>

    <p v-if="loading" class="status" role="status">
      Writing the notice in three languages… this usually takes 10–15 seconds.
    </p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <template v-if="result && !loading">
      <p v-if="result.fallback" class="warn" role="status">
        The AI is busy right now, so this is a plain English version from a template.
        Hindi and Punjabi aren't available — try <strong>Write again</strong> in a minute.
      </p>

      <div class="tabs" role="group" aria-label="Language">
        <button
          v-for="l in LANGS"
          :key="l.id"
          type="button"
          :aria-pressed="lang === l.id"
          :class="{ active: lang === l.id }"
          :disabled="!texts[l.id]"
          @click="lang = l.id"
        >
          {{ l.label }}
        </button>
      </div>

      <label class="visually-hidden" for="circular-text">Notice text (editable)</label>
      <textarea
        id="circular-text"
        v-model="texts[lang]"
        :lang="lang"
        rows="12"
      ></textarea>

      <div class="actions">
        <button type="button" @click="copy">{{ copied ? 'Copied ✓' : 'Copy' }}</button>
        <a class="whatsapp" :href="whatsappUrl" target="_blank" rel="noopener">Share on WhatsApp</a>
      </div>

      <p class="muted small">
        Facts come from the UrbanWise forecast<span v-if="!result.fallback">; wording by Gemini</span>.
        Please read and edit before sending.
      </p>
    </template>
  </dialog>
</template>

<style scoped>
.dialog {
  width: min(640px, calc(100vw - 32px));
  max-height: calc(100dvh - 32px);
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.3);
}

.dialog::backdrop { background: rgba(10, 14, 20, 0.55); }

.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.head h2 { margin: 0; font-size: 1.1rem; }

.icon {
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: var(--surface-2);
  cursor: pointer;
}

.setup label { display: block; font-weight: 600; margin-bottom: 6px; }

.setup p { margin: 6px 0 0; }

.row { display: flex; gap: 8px; }

.row input {
  flex: 1;
  min-width: 0;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}

button, .whatsapp {
  padding: 9px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  cursor: pointer;
  text-decoration: none;
  color: inherit;
  font-weight: 600;
  white-space: nowrap;
}

button:disabled { opacity: 0.5; cursor: default; }

.primary { background: var(--brand); border-color: var(--brand); color: var(--surface); }

.whatsapp { background: #25D366; border-color: #25D366; color: #0B2914; }

.status, .warn, .error {
  margin: 14px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
}

.status { background: var(--surface-2); }

.warn { background: color-mix(in srgb, #FF9900 16%, transparent); }

.error { background: color-mix(in srgb, #E5484D 14%, transparent); }

.tabs {
  display: flex;
  gap: 4px;
  margin: 16px 0 8px;
  padding: 4px;
  background: var(--surface-2);
  border-radius: 10px;
}

.tabs button {
  flex: 1;
  border: 0;
  background: transparent;
  color: var(--muted);
}

.tabs button.active { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12); }

textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  font: inherit;
  line-height: 1.6;
  resize: vertical;
}

.actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
