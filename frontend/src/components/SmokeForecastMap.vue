<script setup>
// "What's coming": forward smoke paths from today's fire clusters.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import Icon3D from './Icon3D.vue'
import { formatInZone } from '../lib/aqi'
import { escapeHtml } from '../lib/html'
import { forecastHeadline, localFiresNote } from '../lib/smokeForecast'

const props = defineProps({
  place: { type: Object, required: true },
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  timeZone: { type: String, default: 'Asia/Kolkata' },
})
const emit = defineEmits(['retry'])

const mapEl = ref(null)
let map = null
let layers = null

const incoming = computed(() => props.data?.alert.incoming)
const headline = computed(() => forecastHeadline(props.data, props.place.name, props.timeZone))
const localNote = computed(() => localFiresNote(props.data))
const arriving = computed(() => (props.data?.clusters || [])
  .filter((c) => c.arrival_h != null && c.arrival_time)
  .sort((a, b) => a.arrival_h - b.arrival_h))

const HOT = '#E8590C'
const COLD = '#9AA4B8'

function draw() {
  if (!map || !props.data) return
  layers.clearLayers()
  const bounds = L.latLngBounds([[props.place.lat, props.place.lon]])

  // Non-arriving paths first (underneath), faded.
  const sorted = [...(props.data.clusters || [])].filter((c) => c.path?.length).sort((a, b) => (a.arrival_h != null) - (b.arrival_h != null))
  for (const c of sorted) {
    const hits = c.arrival_h != null
    const pts = c.path.map(([lat, lon]) => [lat, lon])
    L.polyline(pts, {
      color: hits ? HOT : COLD,
      weight: hits ? 4 : 2.5,
      opacity: hits ? 0.95 : 0.55,
      dashArray: hits ? '10 8' : '4 8',
      className: hits ? 'march' : '',
    }).addTo(layers)
    L.circleMarker([c.lat, c.lon], {
      radius: Math.min(6 + Math.sqrt(c.fires) * 1.6, 18),
      color: '#FFFFFF', weight: 2, fillColor: hits ? HOT : '#F5A06A', fillOpacity: 0.95,
    }).bindTooltip(
      `<strong>${escapeHtml(c.fires)} fires</strong>${c.district ? ` near ${escapeHtml(c.district)}, ${escapeHtml(c.state)}` : ''}<br>` +
      (hits ? `Smoke likely arrives ~${escapeHtml(formatInZone(c.arrival_time, props.timeZone))}` : `Passes ${escapeHtml(c.closest_km)} km away at closest`),
    ).addTo(layers)
    if (hits) {
      // Label where the smoke first reaches the city.
      const p = c.path.find(([, , h]) => h === c.arrival_h) || c.path.at(-1)
      L.marker([p[0], p[1]], {
        icon: L.divIcon({ className: 'eta', html: `~${escapeHtml(formatInZone(c.arrival_time, props.timeZone))}`, iconSize: null }),
        interactive: false,
      }).addTo(layers)
      pts.forEach((pt) => bounds.extend(pt))
    }
    bounds.extend([c.lat, c.lon])
  }

  L.circleMarker([props.place.lat, props.place.lon], {
    radius: 9, color: '#FFFFFF', weight: 3, fillColor: '#22357A', fillOpacity: 1,
  }).bindTooltip(escapeHtml(props.place.name), { permanent: true, direction: 'right', className: 'trail-label city' }).addTo(layers)

  // No animation: an in-flight zoom crashes Leaflet if the view is switched mid-way.
  map.fitBounds(bounds.pad(0.12), { maxZoom: 8, animate: false })
}

onMounted(() => {
  map = L.map(mapEl.value, { scrollWheelZoom: false, zoomSnap: 0.5 }).setView([props.place.lat, props.place.lon], 6)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 12,
  }).addTo(map)
  layers = L.layerGroup().addTo(map)
  draw()
})

watch(() => props.data, draw)
onBeforeUnmount(() => map?.remove())
</script>

<template>
  <section class="card forecast" aria-labelledby="forecast-title">
    <div class="card-head">
      <Icon3D :name="incoming ? 'fire' : 'wind_face'" :size="48" />
      <div>
        <h2 id="forecast-title">Incoming Smoke Alert</h2>
        <p class="muted small">Today's fires, carried forward on the next 48 hours of forecast winds.</p>
      </div>
    </div>

    <div v-if="error" class="error small" role="alert">
      {{ error }} <button type="button" @click="emit('retry')">Try again</button>
    </div>

    <div v-if="data" class="summary" :class="{ incoming }" aria-live="polite">
      <p class="headline">{{ headline }}</p>
      <ul v-if="arriving.length" class="arrivals">
        <li v-for="c in arriving" :key="`${c.lat},${c.lon}`">
          <strong>~{{ formatInZone(c.arrival_time, timeZone) }}</strong>
          · {{ c.fires }} fires{{ c.district ? ` near ${c.district}, ${c.state}` : '' }}
        </li>
      </ul>
      <p v-if="localNote" class="muted small">{{ localNote }}</p>
    </div>
    <p v-else-if="loading" class="muted">Running today's fires forward on the forecast winds…</p>

    <div ref="mapEl" class="map" role="region" :aria-label="headline || 'Map of forecast smoke paths'"></div>

    <div class="legend small muted">
      <span><i class="line hot"></i>Smoke path reaching {{ place.name }}</span>
      <span><i class="line cold"></i>Smoke path passing by</span>
      <span><i class="dot"></i>Fire cluster (size = number of fires)</span>
    </div>
    <p class="muted small footnote">
      Forward trajectories from fires seen by NASA satellites in the last 36 hours, using forecast winds ~750 m up
      (Open-Meteo). Shows smoke that is <strong>likely</strong> to arrive — forecasts can change.
    </p>
  </section>
</template>

<style scoped>
.summary {
  margin: 14px 0 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #F1FBF3;
}

.summary.incoming { background: #FFF0E3; }

.summary p { margin: 0 0 4px; }

.headline { font-size: 1.08rem; font-weight: 700; }

.arrivals { margin: 6px 0; padding-left: 18px; }

.map { height: 440px; border-radius: 12px; border: 1px solid var(--border); z-index: 0; }

.map :deep(.leaflet-tile-pane) { filter: grayscale(0.85) contrast(0.9) brightness(1.05); }

.map :deep(.march) { animation: march 1.1s linear infinite; }

@keyframes march { to { stroke-dashoffset: -18; } }

.map :deep(.eta) {
  padding: 2px 8px;
  border-radius: 999px;
  background: #C2410C; /* dark enough for white 12px text */
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  box-shadow: 0 4px 10px -4px rgba(0, 0, 0, 0.4);
}

.map :deep(.trail-label) { padding: 1px 6px; font-size: 12px; font-weight: 600; }

.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 10px; }

.legend span { display: inline-flex; align-items: center; gap: 6px; }

.line { display: inline-block; width: 22px; height: 0; border-top: 3px dashed; }

.line.hot { border-color: #E8590C; }

.line.cold { border-color: #9AA4B8; }

.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #E8590C; }

.footnote { margin: 10px 0 0; }

.error { display: flex; gap: 8px; align-items: center; color: #B42318; margin: 12px 0; }

@media (max-width: 560px) { .map { height: 340px; } }

@media (prefers-reduced-motion: reduce) { .map :deep(.march) { animation: none; } }
</style>
