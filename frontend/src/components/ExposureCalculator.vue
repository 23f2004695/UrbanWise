<script setup>
import { computed, ref } from 'vue'
import { relativeHour } from '../lib/aqi'
import {
  ACTIVITIES, PEOPLE, exposure, formatCigarettes, formatDuration, savingPercent,
} from '../lib/exposure'
import Icon3D from './Icon3D.vue'

const props = defineProps({
  air: { type: Object, default: null },
  now: { type: String, default: '' }, // real city time
})

const hours = ref(1)
const activity = ref('walking')
const person = ref('child')

// "Now" uses the current hour's PM2.5, not the 24 h average on the main card.
const pm25Now = computed(() => props.air?.current.pm25_now ?? props.air?.current.pm25)
const best = computed(() => props.air?.best_hour)

const result = computed(() => pm25Now.value == null ? null : exposure({
  pm25: pm25Now.value, hours: hours.value, activity: activity.value, person: person.value,
}))

const saving = computed(() => savingPercent(pm25Now.value, best.value?.pm25))

const LEVEL_COLOURS = {
  low: '#00B050',
  moderate: '#FFD60A',
  high: '#FF9900',
  'very-high': '#E00000',
}

const bestLabel = (time) => relativeHour(time, props.now || props.air?.current?.time)
</script>

<template>
  <section class="card exposure" aria-labelledby="exposure-title">
    <div class="card-head">
      <Icon3D name="lungs" :size="46" :delay="1.6" />
      <div>
        <h2 id="exposure-title">How much will I breathe in?</h2>
        <p class="muted small">Estimate the pollution you'd inhale if you go out now.</p>
      </div>
    </div>

    <div v-if="result" class="grid">
      <form class="inputs" @submit.prevent>
        <label class="field">
          <span>Time outside: <strong>{{ formatDuration(hours) }}</strong></span>
          <input v-model.number="hours" type="range" min="0.25" max="8" step="0.25" />
        </label>

        <fieldset class="field">
          <legend>Doing what?</legend>
          <div class="chips">
            <label v-for="(a, key) in ACTIVITIES" :key="key" :class="{ on: activity === key }">
              <input v-model="activity" type="radio" name="activity" :value="key" />
              {{ a.label }}
            </label>
          </div>
        </fieldset>

        <fieldset class="field">
          <legend>Who?</legend>
          <div class="chips">
            <label v-for="(p, key) in PEOPLE" :key="key" :class="{ on: person === key }">
              <input v-model="person" type="radio" name="person" :value="key" />
              {{ p.label }}
            </label>
          </div>
        </fieldset>
      </form>

      <div class="result" aria-live="polite">
        <p class="cigs">
          <span class="big">≈ {{ formatCigarettes(result.cigarettes) }}</span>
          <span>cigarette{{ result.cigarettes >= 0.95 && result.cigarettes < 1.05 ? '' : 's' }} worth of PM2.5</span>
        </p>
        <p class="level">
          <span class="dot" :style="{ background: LEVEL_COLOURS[result.level] }" aria-hidden="true"></span>
          <strong>{{ result.label }} risk</strong>
          <span v-if="person !== 'adult'" class="muted small">(adjusted for {{ PEOPLE[person].label.toLowerCase() }})</span>
        </p>
        <p>{{ result.advice }}</p>
        <p v-if="saving && best" class="tip">
          Going at <strong>{{ bestLabel(best.time) }}</strong> instead would cut this by about <strong>{{ saving }}%</strong>.
        </p>
        <p class="muted small footnote">
          Based on PM2.5 now ({{ Math.round(pm25Now) }} µg/m³). Rule of thumb from Berkeley Earth:
          breathing 22 µg/m³ for a day ≈ 1 cigarette. An estimate, not medical advice.
        </p>
      </div>
    </div>

    <div v-else class="skeleton" aria-hidden="true"></div>
  </section>
</template>

<style scoped>
.exposure { container-type: inline-size; }

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
  margin-top: 16px;
}

/* Side by side only when the card itself is wide enough. */
@container (min-width: 720px) {
  .grid { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; }
}

.inputs { display: grid; gap: 16px; }

.field { display: grid; gap: 6px; margin: 0; padding: 0; border: 0; }

.field legend { padding: 0; margin-bottom: 6px; }

input[type='range'] { width: 100%; accent-color: var(--accent); }

.chips { display: flex; flex-wrap: wrap; gap: 6px; }

.chips label {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.9rem;
}

.chips label.on {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 14%, transparent);
  font-weight: 600;
}

.chips label:has(input:focus-visible) { outline: 2px solid var(--focus); outline-offset: 2px; }

.chips input { position: absolute; opacity: 0; pointer-events: none; }

.result {
  padding: 16px;
  border-radius: 12px;
  background: var(--surface-2);
}

.result p { margin: 0 0 8px; }

.cigs { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }

.big { font-size: 2.4rem; font-weight: 800; line-height: 1.1; }

.level { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }

.dot { width: 12px; height: 12px; border-radius: 50%; }

.tip {
  padding: 8px 10px;
  border-left: 3px solid var(--accent);
  background: var(--surface);
  border-radius: 6px;
}

.footnote { margin-top: 12px !important; }

.skeleton {
  height: 200px;
  margin-top: 16px;
  border-radius: 10px;
  background: var(--surface-2);
}
</style>
