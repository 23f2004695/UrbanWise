<script setup>
// Compact Incoming Smoke Alert, shown on Overview and School.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import Icon3D from './Icon3D.vue'
import { forecastHeadline } from '../lib/smokeForecast'

const props = defineProps({
  data: { type: Object, default: null },
  place: { type: Object, required: true },
  timeZone: { type: String, default: 'Asia/Kolkata' },
  link: { type: Object, default: null },
})

const incoming = computed(() => props.data?.alert.incoming)
const text = computed(() => forecastHeadline(props.data, props.place.name, props.timeZone))
</script>

<template>
  <div v-if="data" class="banner" :class="{ incoming }" role="status">
    <Icon3D :name="incoming ? 'fire' : 'wind_face'" :size="38" />
    <div class="body">
      <p class="label">{{ incoming ? 'Incoming smoke · model estimate' : 'Smoke outlook · next 48 h' }}</p>
      <p class="text">{{ text }}</p>
    </div>
    <RouterLink v-if="link" :to="link" class="see">See forecast →</RouterLink>
  </div>
</template>

<style scoped>
.banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  border: 1px solid #CFE3D4;
  border-radius: var(--radius);
  background: linear-gradient(120deg, #F1FBF3, #FFFFFF);
}

.banner.incoming {
  border-color: #FFC9A3;
  background: linear-gradient(120deg, #FFF0E3, #FFF8F2);
  box-shadow: 0 10px 24px -16px rgba(242, 106, 27, 0.7);
}

.body { flex: 1; min-width: 0; }

.body p { margin: 0; }

.label {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #137333;
}

.incoming .label { color: var(--accent-ink); }

.text { font-weight: 600; }

.see { flex: none; color: var(--brand); font-weight: 650; text-decoration: none; white-space: nowrap; }

@media (max-width: 560px) {
  .banner { flex-wrap: wrap; }
  /* Take the full row next to the icon, so "See forecast" wraps below
     instead of squeezing the text into a narrow column. */
  .body { flex-basis: calc(100% - 52px); }
  .see { margin-left: 52px; }
}
</style>
