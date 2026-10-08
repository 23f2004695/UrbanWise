<script setup>
import { computed } from 'vue'
import { categoryStyle, formatHour } from '../lib/aqi'
import { bestWindow, ventilationAdvice } from '../lib/ventilation'
import Icon3D from './Icon3D.vue'

const props = defineProps({
  air: { type: Object, required: true },
  now: { type: String, default: '' }, // real city time
})

const window_ = computed(() => bestWindow(props.air.forecast || [], props.now || props.air.current?.time || ''))
const advice = computed(() => window_.value && ventilationAdvice(window_.value.aqi))
const style = computed(() => categoryStyle(window_.value?.category))

const when = computed(() => {
  const w = window_.value
  if (!w) return ''
  const end = formatHour(`${w.start.slice(0, 11)}${String(w.endHour % 24).padStart(2, '0')}:00`)
  return `${w.day === 'today' ? 'Today' : 'Tomorrow'}, ${formatHour(w.start)} – ${end}`
})

const TIPS = [
  'Turn on the kitchen exhaust while cooking, especially when frying.',
  'Skip incense, mosquito coils and indoor smoking on bad-air days.',
  'Wet-mop instead of sweeping so settled dust isn\'t thrown back into the air.',
  'No purifier? A box fan with a filter (MERV 13 or better) taped to the back makes a low-cost one.',
]
</script>

<template>
  <section class="card vent" aria-labelledby="vent-title">
    <div class="card-head">
      <Icon3D name="window" :size="46" :delay="2.2" />
      <div>
        <h2 id="vent-title">When to open your windows</h2>
        <p class="muted small">Indoor air gets stale with windows shut all day. Open them during the cleanest hours.</p>
      </div>
    </div>

    <div v-if="window_" class="best">
      <span class="pill" :style="{ background: style.bg, color: style.fg }">AQI {{ window_.aqi }}</span>
      <div>
        <p class="when">{{ when }}</p>
        <p><strong>{{ advice.title }}.</strong> {{ advice.text }}</p>
      </div>
    </div>
    <p v-else class="muted">Not enough forecast data to suggest a time.</p>

    <details class="tips">
      <summary>More ways to keep indoor air clean</summary>
      <ul>
        <li v-for="tip in TIPS" :key="tip">{{ tip }}</li>
      </ul>
    </details>
  </section>
</template>

<style scoped>
.best {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-top: 14px;
  padding: 14px;
  border-radius: 12px;
  background: var(--surface-2);
}

.best p { margin: 0 0 4px; }

.pill {
  flex: none;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  white-space: nowrap;
}

.when { font-size: 1.15rem; font-weight: 700; }

.tips { margin-top: 12px; }

.tips summary { cursor: pointer; color: var(--muted); font-size: 0.9rem; }

.tips ul { margin: 8px 0 0; padding-left: 20px; font-size: 0.9rem; }

.tips li { margin-bottom: 4px; }
</style>
