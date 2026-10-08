<script setup>
import { ref, watch } from 'vue'
import { searchPlaces } from '../composables/useAirData'

const emit = defineEmits(['select'])

const query = ref('')
const results = ref([])
const open = ref(false)
const active = ref(-1)
let timer = null
let latest = 0

watch(query, (q) => {
  clearTimeout(timer)
  if (q.trim().length < 2) {
    latest++ // invalidate any request still in flight, or it would reopen the list
    results.value = []
    open.value = false
    return
  }
  timer = setTimeout(async () => {
    const request = ++latest
    try {
      const found = await searchPlaces(q.trim())
      if (request !== latest) return
      results.value = found
      active.value = found.length ? 0 : -1
      open.value = true
    } catch {
      if (request === latest) results.value = []
    }
  }, 250)
})

function choose(place) {
  emit('select', place)
  query.value = ''
  results.value = []
  open.value = false
}

function onKey(e) {
  if (!open.value || !results.value.length) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    active.value = (active.value + 1) % results.value.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    active.value = (active.value - 1 + results.value.length) % results.value.length
  } else if (e.key === 'Enter' && active.value >= 0) {
    e.preventDefault()
    choose(results.value[active.value])
  } else if (e.key === 'Escape') {
    open.value = false
  }
}
</script>

<template>
  <div class="search">
    <label for="city-search" class="visually-hidden">Search for an Indian city</label>
    <input
      id="city-search"
      v-model="query"
      type="search"
      placeholder="Search a city, e.g. Ludhiana"
      autocomplete="off"
      role="combobox"
      aria-controls="city-results"
      aria-autocomplete="list"
      :aria-expanded="open"
      :aria-activedescendant="open && active >= 0 ? `city-opt-${active}` : undefined"
      @keydown="onKey"
      @blur="open = false"
    />
    <ul v-if="open" id="city-results" class="results" role="listbox">
      <li v-if="!results.length" class="empty">No matching places in India</li>
      <li
        v-for="(place, i) in results"
        :id="`city-opt-${i}`"
        :key="`${place.lat},${place.lon}`"
        role="option"
        :aria-selected="i === active"
        :class="{ active: i === active }"
        @mousedown.prevent="choose(place)"
      >
        <strong>{{ place.name }}</strong>
        <span class="muted small">{{ place.region }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.search { position: relative; width: 100%; max-width: 360px; }

input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
}

.results {
  position: absolute;
  z-index: 10;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  margin: 0;
  padding: 6px;
  list-style: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

li {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
}

li.active { background: var(--surface-2); }

li.empty { cursor: default; color: var(--muted); }

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
