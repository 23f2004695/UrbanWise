<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { escapeHtml } from '../lib/html'
import InfoToggle from './InfoToggle.vue'
import { fireRadius, trailDetail, trailHeadline } from '../lib/smokeTrail'
import Icon3D from './Icon3D.vue'

const props = defineProps({
  place: { type: Object, required: true },
  data: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['retry'])

const mapEl = ref(null)
let map = null
let layers = null
let frame = null

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')

const summary = computed(() => props.data?.summary)
const headline = computed(() => trailHeadline(summary.value, props.place.name))
const detail = computed(() => trailDetail(summary.value))

const TRAIL_COLOUR = '#7B61FF'
const FIRE_COLOUR = '#FF6B1A'

function draw() {
  if (!map || !props.data) return
  cancelAnimationFrame(frame)
  layers.clearLayers()

  const trail = props.data.trail || []
  const fires = props.data.fires || []
  const nearby = props.data.nearby_fires || []
  if (!trail.length) return

  // Other fires in the area, faded, so the matched ones stand out.
  for (const f of nearby) {
    L.circleMarker([f.lat, f.lon], {
      radius: 3, stroke: false, fillColor: '#8A94A6', fillOpacity: 0.45, interactive: false,
    }).addTo(layers)
  }

  // Trail runs from the oldest point to the city, so it reads as smoke arriving.
  const ordered = [...trail].reverse()
  const line = L.polyline([], { color: TRAIL_COLOUR, weight: 4, opacity: 0.9 }).addTo(layers)

  for (const [lat, lon, h] of trail) {
    if (h > 0 && h % 12 === 0) {
      L.circleMarker([lat, lon], {
        radius: 4, color: TRAIL_COLOUR, weight: 2, fillColor: '#FFFFFF', fillOpacity: 1,
      }).bindTooltip(`${h} h ago`, { permanent: h % 24 === 0, direction: 'top', className: 'trail-label' })
        .addTo(layers)
    }
  }

  for (const f of fires) {
    const where = f.district ? `${escapeHtml(f.district)}, ${escapeHtml(f.state)}` : 'Outside mapped districts'
    L.circleMarker([f.lat, f.lon], {
      radius: fireRadius(f.frp), color: '#FFFFFF', weight: 1, fillColor: FIRE_COLOUR, fillOpacity: 0.9,
    }).bindTooltip(`<strong>Fire</strong> · ${where}<br>Detected ~${escapeHtml(f.hours_ago)} h ago · intensity ${escapeHtml(f.frp)} MW`)
      .addTo(layers)
  }

  L.circleMarker([trail[0][0], trail[0][1]], {
    radius: 8, color: '#FFFFFF', weight: 3, fillColor: TRAIL_COLOUR, fillOpacity: 1,
  }).bindTooltip(escapeHtml(props.place.name), { permanent: true, direction: 'right', className: 'trail-label city' })
    .addTo(layers)

  const bounds = L.latLngBounds(trail.map(([lat, lon]) => [lat, lon]))
  fires.forEach((f) => bounds.extend([f.lat, f.lon]))
  // No animation: an in-flight zoom crashes Leaflet if the view is switched mid-way.
  map.fitBounds(bounds.pad(0.15), { maxZoom: 9, animate: false })

  const points = ordered.map(([lat, lon]) => [lat, lon])
  if (reducedMotion.matches) {
    line.setLatLngs(points)
    return
  }
  // Reveal the trail over ~2.5 s.
  const start = performance.now()
  const duration = 2500
  const step = (now) => {
    const t = Math.min((now - start) / duration, 1)
    line.setLatLngs(points.slice(0, Math.max(2, Math.ceil(t * points.length))))
    if (t < 1) frame = requestAnimationFrame(step)
  }
  frame = requestAnimationFrame(step)
}

onMounted(() => {
  map = L.map(mapEl.value, { scrollWheelZoom: false, zoomSnap: 0.5 })
    .setView([props.place.lat, props.place.lon], 6)
  // OpenStreetMap tiles need no key; dark mode is handled with a CSS filter.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 12,
  }).addTo(map)
  layers = L.layerGroup().addTo(map)
  draw()
})

watch(() => props.data, draw)

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  map?.remove()
})
</script>

<template>
  <section class="card trail" aria-labelledby="trail-title">
    <div class="head">
      <div class="card-head">
        <Icon3D name="fire" :size="48" :delay="0.9" />
        <div>
        <h2 id="trail-title">Smoke Trail</h2>
        </div>
      </div>
      <button v-if="data && !loading" type="button" class="replay" @click="draw">Replay</button>
      <span v-else-if="loading" class="muted small">Tracing…</span>
    </div>

    <div v-if="error" class="error small" role="alert">
      {{ error }}
      <button type="button" @click="emit('retry')">Try again</button>
    </div>

    <div v-if="summary" class="summary" aria-live="polite">
      <p class="headline">{{ headline }}</p>
      <p class="muted">{{ detail }}</p>
      <ul v-if="summary.top_districts.length" class="districts">
        <li v-for="d in summary.top_districts" :key="d.district" :title="d.state">
          <strong>{{ d.district }}</strong><span class="muted"> · {{ d.fires }}</span>
        </li>
        <li v-if="summary.other_fires" class="muted">+{{ summary.other_fires }} elsewhere</li>
      </ul>
    </div>

    <div class="map-wrap">
      <div ref="mapEl" class="map" role="region" :aria-label="headline || 'Map of the air trail and nearby fires'"></div>
      <div v-if="loading && !data" class="map-loading muted small">Tracing the air backwards…</div>
    </div>

    <div class="legend small muted">
      <span><i class="line"></i>Air's path</span>
      <span><i class="dot fire"></i>Fire on the path</span>
      <span><i class="dot other"></i>Other fires</span>
    </div>

    <InfoToggle>
      <p>
        UrbanWise traces the air back 48 hours on winds ~750 m up (Open-Meteo) and matches fires seen by NASA
        satellites (FIRMS VIIRS) along the way. Dots on the path mark every 12 hours; fire size shows intensity.
      </p>
      <p>
        A simplified estimate: these are <strong>likely</strong> contributing sources, not exact shares. Satellite
        fires are heat detections — in Oct–Nov in Punjab and Haryana mostly crop-residue burning.
      </p>
      <p>
        This uses one weather model. When we checked it against NOAA HYSPLIT, a different weather model often named
        different fires, so treat the districts as a rough guide.
      </p>
    </InfoToggle>
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

.replay {
  flex: none;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  cursor: pointer;
}

.summary { margin: 14px 0 12px; }

.summary p { margin: 0 0 4px; }

.headline { font-size: 1.1rem; font-weight: 650; }

.districts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.9rem;
}

.map-wrap { position: relative; }

.map {
  height: 420px;
  border-radius: 12px;
  border: 1px solid var(--border);
  z-index: 0;
}

.map-loading {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--surface) 70%, transparent);
  border-radius: 12px;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 18px;
  margin-top: 10px;
}

.legend span { display: inline-flex; align-items: center; gap: 6px; }

.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }

.dot.city { background: #7B61FF; box-shadow: 0 0 0 2px #FFFFFF inset; }

.dot.fire { background: #FF6B1A; }

.dot.other { background: #8A94A6; opacity: 0.6; }

.line { display: inline-block; width: 18px; height: 4px; border-radius: 2px; background: #7B61FF; }

.error {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
  color: #B42318;
}

.error button {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  cursor: pointer;
}

@media (max-width: 560px) {
  .map { height: 340px; }
}

/* Calmer basemap so the trail and fires stand out; inverted in dark mode. */
.map :deep(.leaflet-tile-pane) { filter: grayscale(0.85) contrast(0.9) brightness(1.05); }

:deep(.trail-label) {
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
}

:deep(.trail-label.city) { font-size: 12px; }
</style>
