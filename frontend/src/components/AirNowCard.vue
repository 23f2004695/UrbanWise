<script setup>
import { computed } from 'vue'
import { categoryStyle, POLLUTANT_NAMES, relativeHour } from '../lib/aqi'
import Icon3D from './Icon3D.vue'
import { tilt as vTilt } from '../lib/tilt'

const props = defineProps({
  place: { type: Object, required: true },
  air: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  now: { type: String, default: '' }, // real city time, "YYYY-MM-DDTHH:MM"
})

const current = computed(() => props.air?.current)
const style = computed(() => categoryStyle(current.value?.category))

// A face that matches the air: relaxed when clean, masked when it's bad.
const mood = computed(() => {
  const aqi = current.value?.aqi
  if (aqi == null) return 'fog'
  if (aqi <= 100) return 'smiling_face_with_sunglasses'
  if (aqi <= 200) return 'fog'
  return 'face_with_medical_mask'
})

// The window is the next 24 h, so say "tomorrow" when the hour falls there.
const when = (time) => relativeHour(time, props.now || current.value?.time)
</script>

<template>
  <section class="card now" aria-live="polite">
    <div class="head">
      <div class="card-head">
        <Icon3D :name="mood" :size="48" />
        <div>
          <h2>Today's Air · {{ place.name }}</h2>
          <p class="muted small">{{ place.region || 'India' }}</p>
        </div>
      </div>
      <span v-if="loading" class="muted small">Updating…</span>
    </div>

    <div v-if="current" class="body">
      <div v-tilt="14" class="badge" :style="{ '--c': style.bg, color: style.fg }">
        <span class="aqi">{{ current.aqi }}</span>
        <span class="label">AQI</span>
      </div>

      <div class="details">
        <p class="category">{{ current.category }}</p>
        <p class="advice">{{ current.advice }}</p>
        <p class="muted small">
          Main pollutant: <strong>{{ POLLUTANT_NAMES[current.dominant] }}</strong>
          · PM2.5 {{ current.pm25 }} µg/m³ · PM10 {{ current.pm10 }} µg/m³
        </p>
        <p v-if="air.best_hour || air.worst_hour" class="hours small">
          <span v-if="air.best_hour">Best time outside: <strong>{{ when(air.best_hour.time) }}</strong> (AQI {{ air.best_hour.aqi }})</span>
          <span v-if="air.worst_hour">Worst: <strong>{{ when(air.worst_hour.time) }}</strong> (AQI {{ air.worst_hour.aqi }})</span>
        </p>
      </div>
    </div>

    <div v-else-if="loading" class="skeleton" aria-hidden="true"></div>

    <p v-if="current" class="muted small footnote">
      Indian CPCB scale · {{ current.basis }} · Source: {{ current.source }}
    </p>
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

.body {
  display: flex;
  gap: 24px;
  align-items: center;
  margin-top: 16px;
}

.badge {
  position: relative;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 128px;
  height: 128px;
  border-radius: 50%;
  /* Glossy 3D sphere: highlight top-left, shade bottom-right, soft shadow. */
  background:
    radial-gradient(circle at 32% 28%, rgba(255, 255, 255, 0.75), transparent 34%),
    radial-gradient(circle at 70% 78%, rgba(0, 0, 0, 0.22), transparent 55%),
    var(--c);
  box-shadow:
    inset -8px -10px 18px rgba(0, 0, 0, 0.18),
    inset 6px 8px 14px rgba(255, 255, 255, 0.35),
    0 14px 26px -8px color-mix(in srgb, var(--c) 70%, black);
  animation: breathe 4.5s ease-in-out infinite;
}

/* Soft halo pulsing outward, like the air "breathing". */
.badge::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 60%, transparent);
  animation: halo 4.5s ease-out infinite;
}

@keyframes breathe {
  0%, 100% { scale: 1; }
  50% { scale: 1.04; }
}

@keyframes halo {
  0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 55%, transparent); }
  70%, 100% { box-shadow: 0 0 0 18px transparent; }
}

@media (prefers-reduced-motion: reduce) {
  .badge, .badge::after { animation: none; }
}

.aqi { font-size: 2.75rem; font-weight: 800; line-height: 1; }

.label { font-size: 0.8rem; font-weight: 600; letter-spacing: 0.08em; }

.details p { margin: 0 0 6px; }

.category { font-size: 1.5rem; font-weight: 700; }

.advice { font-size: 1.05rem; }

.hours {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  margin-top: 10px !important;
}

.footnote { margin: 16px 0 0; }

.skeleton {
  height: 128px;
  margin-top: 16px;
  border-radius: 10px;
  background: var(--surface-2);
}

@media (max-width: 560px) {
  .body { flex-direction: column; align-items: flex-start; gap: 16px; }
  .badge { width: 104px; height: 104px; }
  .aqi { font-size: 2.25rem; }
}
</style>
