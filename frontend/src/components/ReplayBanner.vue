<script setup>
// Always-visible label for demo replay: replayed data must never look live.
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { replayInfo } from '../lib/replay'

const props = defineProps({
  date: { type: String, required: true },
  place: { type: Object, required: true },
  timeZone: { type: String, default: 'Asia/Kolkata' },
  exitTo: { type: Object, required: true },
})
const emit = defineEmits(['select'])

const info = computed(() => replayInfo(props.date))
const captured = computed(() => {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: props.timeZone, day: 'numeric', month: 'short', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
    }).format(new Date(info.value.capturedUtc))
  } catch {
    return info.value.label
  }
})
const same = (c) => Math.abs(c.lat - props.place.lat) < 0.01 && Math.abs(c.lon - props.place.lon) < 0.01
</script>

<template>
  <div v-if="info" class="replay" role="status">
    <span class="tag">🎬 DEMO REPLAY</span>
    <p class="what">
      <strong>Not live.</strong> Real data captured {{ captured }} IST, replayed for demonstration.
    </p>
    <div class="cities" role="group" aria-label="Replay city">
      <button
        v-for="c in info.cities"
        :key="c.name"
        type="button"
        :aria-pressed="same(c)"
        :class="{ on: same(c) }"
        @click="emit('select', c)"
      >{{ c.name }}</button>
    </div>
    <RouterLink :to="exitTo" class="exit">Exit to live data →</RouterLink>
  </div>
</template>

<style scoped>
.replay {
  position: sticky;
  top: 8px;
  z-index: 950;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  padding: 10px 14px;
  border: 2px solid #B54708;
  border-radius: 14px;
  background:
    repeating-linear-gradient(135deg, rgba(255, 214, 10, 0.18) 0 12px, transparent 12px 24px),
    #FFF7E0;
  box-shadow: 0 10px 24px -14px rgba(181, 71, 8, 0.6);
}

.tag {
  padding: 3px 10px;
  border-radius: 999px;
  background: #B54708;
  color: #fff;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.05em;
}

.what { margin: 0; flex: 1 1 260px; color: #5C2D00; }

.cities { display: flex; flex-wrap: wrap; gap: 6px; }

.cities button {
  padding: 5px 12px;
  border: 1px solid #E8C48A;
  border-radius: 999px;
  background: #fff;
  font-weight: 600;
  cursor: pointer;
}

.cities button.on { background: #B54708; border-color: #B54708; color: #fff; }

.exit { color: #5C2D00; font-weight: 700; white-space: nowrap; }
</style>
