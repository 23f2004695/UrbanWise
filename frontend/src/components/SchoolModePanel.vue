<script setup>
import { computed, ref, watch } from 'vue'
import { formatDay } from '../lib/aqi'
import { daySummary, decisionStyle, isPast } from '../lib/school'
import Icon3D from './Icon3D.vue'

const props = defineProps({
  days: { type: Array, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  now: { type: String, default: '' }, // city-local "YYYY-MM-DDTHH:MM"
  grapApplies: { type: Boolean, default: true }, // GRAP is Delhi-NCR only
})

const emit = defineEmits(['change-times', 'retry', 'write-circular'])

const selected = ref(0)
const userChose = ref(false) // once the user picks a day, don't override it
const day = computed(() => props.days?.[selected.value])

function choose(i) {
  selected.value = i
  userChose.value = true
}

// New data (e.g. another city) resets to the automatic choice.
watch(() => props.days, () => { userChose.value = false })

// Default to tomorrow once today's school day is over. Re-decide only when new
// data arrives or the date changes — not every minute as the clock ticks,
// which used to snap the user's chosen tab back.
watch(() => [props.days, props.now ? props.now.slice(0, 10) : ''], ([days]) => {
  const now = props.now
  if (!days?.length || !now || userChose.value) return
  const lastSlot = days[0].slots.at(-1)
  selected.value = lastSlot && isPast(days[0].date, lastSlot.time, now) ? 1 : 0
}, { immediate: true })

const tabName = (i) => (i === 0 ? 'Today' : 'Tomorrow')
const tabDate = (d) => formatDay(`${d.date}T00:00`)

function onTimeChange(slot, value) {
  if (value) emit('change-times', { [slot.id]: value })
}
</script>

<template>
  <section class="card school" aria-labelledby="school-title">
    <div class="head">
      <div class="card-head">
        <Icon3D name="school" :size="48" :delay="1.1" />
        <div>
        <h2 id="school-title">School Mode</h2>
        <p class="muted small">Can children be outside? UrbanWise guidance based on CPCB AQI categories, checked against each activity's forecast hour — not an official CPCB or school-board rule.</p>
        </div>
      </div>
      <span v-if="loading" class="muted small">Updating…</span>
    </div>

    <div v-if="error" class="error small" role="alert">
      {{ error }}
      <button type="button" @click="emit('retry')">Try again</button>
    </div>

    <template v-else-if="days">
      <div class="tabs" role="group" aria-label="Day">
        <button
          v-for="(d, i) in days"
          :key="d.date"
          type="button"
          :aria-pressed="selected === i"
          :class="{ active: selected === i }"
          @click="choose(i)"
        >
          <span>{{ tabName(i) }}</span>
          <span class="tab-date">{{ tabDate(d) }}</span>
        </button>
      </div>

      <div v-if="day">
        <p class="summary">
          <strong>{{ daySummary(day.slots) }}</strong>
          <span v-if="day.grap_stage && grapApplies" class="grap" title="Graded Response Action Plan — applies to Delhi-NCR">GRAP Stage {{ day.grap_stage }} · Delhi-NCR</span>
        </p>

        <ul class="slots">
          <li
            v-for="slot in day.slots"
            :key="slot.id"
            :class="{ past: selected === 0 && now && isPast(day.date, slot.time, now) }"
          >
            <span
              class="badge"
              :style="{ background: decisionStyle(slot.decision).bg, color: decisionStyle(slot.decision).fg }"
              aria-hidden="true"
            >{{ decisionStyle(slot.decision).symbol }}</span>

            <div class="info">
              <div class="row">
                <strong>{{ slot.label }}</strong>
                <label class="time">
                  <span class="visually-hidden">{{ slot.label }} time</span>
                  <input
                    type="time"
                    step="3600"
                    :value="slot.time"
                    @change="onTimeChange(slot, $event.target.value)"
                  />
                </label>
              </div>
              <p class="decision">
                <strong>{{ slot.verdict }}</strong>
                <span v-if="slot.aqi !== null" class="muted"> · AQI {{ slot.aqi }} ({{ slot.category }})</span>
              </p>
              <p v-if="slot.advice" class="advice small muted">{{ slot.advice }}</p>
            </div>
          </li>
        </ul>

        <button type="button" class="circular" @click="emit('write-circular', day.date)">
          ✉ Write notice to parents for {{ selected === 0 ? 'today' : 'tomorrow' }}
        </button>
      </div>
    </template>

    <div v-else-if="loading" class="skeleton" aria-hidden="true"></div>
  </section>
</template>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.head p { margin: 0; }

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin: 16px 0 12px;
  padding: 4px;
  background: var(--surface-2);
  border-radius: 10px;
}

.tabs button {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  align-items: baseline;
  gap: 0 6px;
  padding: 6px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.tab-date { font-size: 0.85em; opacity: 0.85; }

.tabs button.active {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
}

.summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin: 0 0 12px;
  font-size: 1.05rem;
}

.grap {
  padding: 2px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.8rem;
  color: var(--muted);
}

.slots {
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.slots li {
  display: flex;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
}

.slots li.past { opacity: 0.55; }

.badge {
  flex: none;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-weight: 800;
}

.info { flex: 1; min-width: 0; }

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.time input {
  padding: 2px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
}

.decision { margin: 4px 0 0; }

.circular {
  width: 100%;
  margin-top: 12px;
  padding: 10px 14px;
  border: 0;
  border-radius: 10px;
  background: var(--brand);
  color: var(--surface);
  font-weight: 600;
  cursor: pointer;
}

.advice { margin: 2px 0 0; }

.error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  color: #B42318;
}

.error button {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  cursor: pointer;
}

.skeleton {
  height: 220px;
  margin-top: 16px;
  border-radius: 10px;
  background: var(--surface-2);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
