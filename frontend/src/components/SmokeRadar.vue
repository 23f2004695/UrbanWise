<script setup>
// Smoke Radar: a 48-hour time-lapse of wind, fires and smoke over North India.
// Wind streaks show direction (sped up for visibility); smoke particles move at
// the real time-lapse rate, released from each fire after satellites saw it.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import Icon3D from './Icon3D.vue'
import InfoToggle from './InfoToggle.vue'
import { aqiCategory, categoryStyle, formatInZone } from '../lib/aqi'
import { escapeHtml } from '../lib/html'
import { advect, gridBounds, windAt } from '../lib/radar'

const props = defineProps({
  place: { type: Object, required: true },
  timeZone: { type: String, default: 'Asia/Kolkata' },
})

const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const radar = ref(null)
const loading = ref(false)
const error = ref('')
const frame = ref(0)        // fractional frame (hours since the first frame)
const playing = ref(false)

const mapEl = ref(null)
const canvas = ref(null)
let map = null
let cityLayer = null
let raf = 0
let lastTs = 0
let visible = true
let io = null

const LEFT_LABELS = new Set(['Ludhiana', 'Kanpur'])
const FRAME_MS = 650        // one hour of time-lapse per 0.65 s
const WIND_PARTICLES = 700
const WIND_BOOST = 7        // wind streaks are sped up so direction is visible
const MAX_SMOKE = 2600
const SMOKE_LIFE_H = 30

let wind = []
let smoke = []

const frames = computed(() => radar.value?.frames || [])
const nowIndex = computed(() => radar.value?.now_index ?? 0)
const frameIndex = computed(() => Math.min(Math.floor(frame.value), Math.max(frames.value.length - 1, 0)))
const clock = computed(() => (frames.value.length ? formatInZone(`${frames.value[frameIndex.value]}:00Z`, props.timeZone) : ''))
const phase = computed(() => {
  if (!frames.value.length) return ''
  const d = frameIndex.value - nowIndex.value
  if (d === 0) return 'Now'
  return d < 0 ? `${-d} h ago` : `Forecast · in ${d} h`
})
const firesSeen = computed(() => (radar.value?.fires || []).filter((f) => f.t <= frame.value).length)

async function load() {
  loading.value = true
  error.value = ''
  // A new place: don't keep animating the previous city's radar under its name.
  radar.value = null
  playing.value = false
  smoke = []
  wind = []
  clearCanvas()
  cityLayer?.clearLayers()
  const want = `${props.place.lat},${props.place.lon}`
  try {
    const params = new URLSearchParams({ lat: props.place.lat, lon: props.place.lon })
    const res = await fetch(`/api/radar?${params}`)
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`)
    if (want !== `${props.place.lat},${props.place.lon}`) return
    if (!body.frames?.length || !body.u?.length) throw new Error('No radar data for this area yet.')
    radar.value = body
    frame.value = 0
    resetParticles()
    fitMap()
    drawCities()
    playing.value = !reduced
    if (reduced) {
      frame.value = body.now_index ?? 0
      drawStill()
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

// ---------- particles ----------
function randomInGrid() {
  const [[s, w], [n, e]] = gridBounds(radar.value)
  return [s + Math.random() * (n - s), w + Math.random() * (e - w)]
}

function resetParticles() {
  smoke = []
  wind = Array.from({ length: WIND_PARTICLES }, () => {
    const [lat, lon] = randomInGrid()
    return { lat, lon, age: Math.random() * 60 }
  })
  clearCanvas()
}

function emitSmoke(fromFrame, toFrame) {
  for (const f of radar.value.fires) {
    // Fires seen before the time-lapse started keep smouldering from frame 0.
    const start = Math.max(f.t, 0)
    if (start > toFrame || toFrame - start > 24) continue
    const rate = 0.6 + Math.sqrt(f.frp) * 0.35 // puffs per hour
    let n = rate * (toFrame - Math.max(fromFrame, start))
    while (n > 0 && smoke.length < MAX_SMOKE) {
      if (n < 1 && Math.random() > n) break
      smoke.push({ lat: f.lat + (Math.random() - 0.5) * 0.05, lon: f.lon + (Math.random() - 0.5) * 0.05, born: toFrame })
      n -= 1
    }
  }
}

function step(dtFrames) {
  const r = radar.value
  const t = frame.value
  for (const p of wind) {
    const w = windAt(r, p.lat, p.lon, t)
    p.age += 1
    if (!w || p.age > 70) {
      [p.lat, p.lon] = randomInGrid()
      p.age = 0
      p.prev = null
      continue
    }
    p.prev = [p.lat, p.lon];
    [p.lat, p.lon] = advect(p.lat, p.lon, w, Math.max(dtFrames, 0.02) * WIND_BOOST)
  }
  if (dtFrames > 0) {
    emitSmoke(t - dtFrames, t)
    smoke = smoke.filter((s) => {
      if (t - s.born > SMOKE_LIFE_H) return false
      const w = windAt(r, s.lat, s.lon, t)
      if (!w) return false;
      [s.lat, s.lon] = advect(s.lat, s.lon, w, dtFrames)
      return true
    })
  }
}

// ---------- drawing ----------
function sizeCanvas() {
  const c = canvas.value
  if (!c || !mapEl.value) return
  const dpr = Math.min(window.devicePixelRatio, 2)
  const { clientWidth: w, clientHeight: h } = mapEl.value
  c.width = w * dpr
  c.height = h * dpr
  c.style.width = `${w}px`
  c.style.height = `${h}px`
  c.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0)
}

function clearCanvas() {
  const c = canvas.value
  if (c) c.getContext('2d').clearRect(0, 0, c.width, c.height)
}

function draw() {
  const c = canvas.value
  if (!c || !map || !radar.value) return
  const ctx = c.getContext('2d')
  // Fade the previous frame to leave short trails.
  ctx.globalCompositeOperation = 'destination-out'
  ctx.fillStyle = 'rgba(0, 0, 0, 0.12)'
  ctx.fillRect(0, 0, c.width, c.height)
  ctx.globalCompositeOperation = 'source-over'

  const pt = (lat, lon) => map.latLngToContainerPoint([lat, lon])

  ctx.lineWidth = 1.4
  ctx.strokeStyle = 'rgba(34, 53, 122, 0.62)'
  ctx.beginPath()
  for (const p of wind) {
    if (!p.prev) continue
    const a = pt(p.prev[0], p.prev[1])
    const b = pt(p.lat, p.lon)
    ctx.moveTo(a.x, a.y)
    ctx.lineTo(b.x, b.y)
  }
  ctx.stroke()

  const t = frame.value
  for (const s of smoke) {
    const age = (t - s.born) / SMOKE_LIFE_H // 0 → 1
    const q = pt(s.lat, s.lon)
    const fresh = Math.max(0, 1 - age * 3)
    const r = Math.round(120 + 120 * fresh)
    const g = Math.round(120 + 20 * fresh)
    const bl = Math.round(130 - 100 * fresh)
    ctx.fillStyle = `rgba(${r}, ${g}, ${bl}, ${0.55 * (1 - age)})`
    ctx.beginPath()
    ctx.arc(q.x, q.y, 1.6 + age * 3.2, 0, Math.PI * 2)
    ctx.fill()
  }

  for (const f of radar.value.fires) {
    if (f.t > t || t - Math.max(f.t, 0) > 24) continue
    const q = pt(f.lat, f.lon)
    const flash = f.t >= 0 && t - f.t < 1.5 ? 1 - (t - f.t) / 1.5 : 0
    ctx.fillStyle = `rgba(232, 89, 12, ${0.85})`
    ctx.beginPath()
    ctx.arc(q.x, q.y, 2.4 + flash * 5, 0, Math.PI * 2)
    ctx.fill()
  }
}

let lastCityFrame = -1
function drawCities(force = true) {
  if (!map || !radar.value) return
  const k = frameIndex.value
  if (!force && k === lastCityFrame) return
  lastCityFrame = k
  cityLayer.clearLayers()
  for (const c of radar.value.cities) {
    const aqi = c.aqi[k]
    const style = categoryStyle(aqi != null ? aqiCategory(aqi) : null)
    L.circleMarker([c.lat, c.lon], {
      // markerPane (600) keeps city dots above the smoke particles (450)
      radius: 8, color: '#FFFFFF', weight: 2.5, fillColor: style.bg, fillOpacity: 1, pane: 'markerPane',
    }).bindTooltip(`${escapeHtml(c.name)} <strong>${escapeHtml(aqi ?? '—')}</strong>`, {
      // Ludhiana and Kanpur sit just west of Chandigarh and Lucknow; their labels
      // go on the left so neighbouring labels don't overlap.
      permanent: true, direction: LEFT_LABELS.has(c.name) ? 'left' : 'right', className: 'radar-city',
    }).addTo(cityLayer)
  }
}

function fitMap() {
  // Zoom slightly inside the wind grid so its empty edges aren't shown.
  if (map && radar.value) map.fitBounds(L.latLngBounds(gridBounds(radar.value)).pad(-0.12), { animate: false })
}

// ---------- loop ----------
function loop(ts) {
  raf = requestAnimationFrame(loop)
  if (!visible || !radar.value) { lastTs = ts; return }
  const dtMs = lastTs ? Math.min(ts - lastTs, 50) : 16
  lastTs = ts
  // Paused (or reduced motion without pressing play): the picture stays still.
  if (!playing.value) return
  const dt = dtMs / FRAME_MS
  frame.value += dt
  if (frames.value.length < 2 || frame.value >= frames.value.length - 1) {
    frame.value = 0
    smoke = []
    clearCanvas()
  }
  step(dt)
  draw()
  drawCities(false)
}

// Draw one still frame (after scrubbing, or when paused) without moving time.
function drawStill() {
  if (!radar.value) return
  clearCanvas()
  for (let i = 0; i < 12; i++) { step(0); draw() } // short wind streaks
  drawCities()
}

function togglePlay() {
  playing.value = !playing.value
}

function onScrub(e) {
  frame.value = Number(e.target.value)
  smoke = [] // smoke history no longer matches; it rebuilds as it plays
  drawStill()
}

function jumpToNow() {
  frame.value = nowIndex.value
  smoke = []
  drawStill()
}

onMounted(() => {
  map = L.map(mapEl.value, { scrollWheelZoom: false, zoomSnap: 0.25 }).setView([props.place.lat, props.place.lon], 6)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 10,
  }).addTo(map)
  cityLayer = L.layerGroup().addTo(map)

  // The particle canvas lives in its own Leaflet pane between the map (400)
  // and the city labels (tooltips, 650), so smoke never hides the labels.
  // It's kept aligned with the container's top-left so we can keep drawing in
  // container pixels while the map pans.
  const pane = map.createPane('particles')
  pane.style.zIndex = '450'
  pane.style.pointerEvents = 'none'
  const el = document.createElement('canvas')
  el.className = 'particles'
  el.setAttribute('aria-hidden', 'true')
  pane.appendChild(el)
  canvas.value = el
  const alignCanvas = () => L.DomUtil.setPosition(el, map.containerPointToLayerPoint([0, 0]))

  map.on('movestart zoomstart', clearCanvas)
  map.on('move', alignCanvas)
  map.on('moveend zoomend', () => {
    alignCanvas()
    clearCanvas()
    if (!playing.value) drawStill()
  })
  map.on('resize', () => { sizeCanvas(); alignCanvas() })
  sizeCanvas()
  alignCanvas()
  io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting })
  io.observe(mapEl.value)
  raf = requestAnimationFrame(loop)
  load()
})

watch(() => props.place, load)

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  io?.disconnect()
  map?.remove()
})
</script>

<template>
  <section class="card radar" aria-labelledby="radar-title">
    <div class="card-head">
      <Icon3D name="satellite" :size="48" />
      <div>
        <h2 id="radar-title">
          Smoke Radar
          <span class="tag-estimate" title="Smoke is simulated from fires and winds">simulation</span>
        </h2>
      </div>
    </div>

    <div v-if="error" class="error small" role="alert">{{ error }} <button type="button" @click="load">Try again</button></div>

    <div class="stage">
      <div ref="mapEl" class="map"></div>
      <div v-if="frames.length" class="hud" aria-live="off">
        <span class="hud-clock">{{ clock }}</span>
        <span class="hud-phase" :class="{ forecast: frameIndex > nowIndex, now: frameIndex === nowIndex }">{{ phase }}</span>
        <span class="hud-fires">🔥 {{ firesSeen }} fires detected so far</span>
      </div>
      <div v-if="loading" class="loading muted">Loading 48 hours of winds and fires…</div>
    </div>

    <div v-if="frames.length" class="controls">
      <button type="button" class="play" :aria-label="playing ? 'Pause' : 'Play'" @click="togglePlay">{{ playing ? '❚❚' : '▶' }}</button>
      <div class="track">
        <label for="radar-time" class="visually-hidden">Time</label>
        <input
          id="radar-time"
          type="range"
          min="0"
          :max="frames.length - 1"
          step="1"
          :value="frameIndex"
          @input="onScrub"
        />
        <span v-if="frames.length > 1" class="now-mark" :style="{ left: `${(nowIndex / (frames.length - 1)) * 100}%` }">now</span>
      </div>
      <button type="button" class="btn btn-ghost small-btn" @click="jumpToNow">Now</button>
    </div>

    <div class="legend small muted">
      <span><i class="streak"></i>Wind</span>
      <span><i class="dot fire"></i>Fire</span>
      <span><i class="dot smoke"></i>Smoke</span>
      <span><i class="dot city"></i>City AQI</span>
    </div>
    <InfoToggle>
      <p>
        A 48-hour time-lapse (24 h back, 24 h ahead). Winds ~750 m up and air quality from Open-Meteo (CAMS);
        fires from NASA FIRMS. Wind streaks are sped up so you can see the direction.
      </p>
      <p>
        Smoke is simulated by carrying particles on the wind from each detected fire (orange = fresh, grey = older) —
        an illustration of likely transport, not a measurement.
      </p>
    </InfoToggle>
  </section>
</template>

<style scoped>
/* isolation keeps Leaflet's z-indexes inside this box (below sticky headers).
   The particle canvas is inside Leaflet itself (a custom pane, see onMounted). */
.stage { position: relative; margin-top: 14px; isolation: isolate; }

.map { height: 480px; border-radius: 12px; border: 1px solid var(--border); }

.map :deep(.leaflet-tile-pane) { filter: grayscale(1) contrast(0.85) brightness(1.08); }

.map :deep(.particles) { position: absolute; left: 0; top: 0; pointer-events: none; }

.hud {
  position: absolute;
  z-index: 900;
  top: 12px;
  right: 12px;
  display: grid;
  justify-items: end;
  gap: 4px;
  padding: 10px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(8px);
  box-shadow: 0 8px 20px -12px rgba(23, 33, 58, 0.5);
  pointer-events: none;
}

.hud-clock { font-size: 1.5rem; font-weight: 800; color: var(--brand); font-variant-numeric: tabular-nums; }

.hud-phase { font-size: 0.78rem; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted); }

.hud-phase.now { color: #137333; }

.hud-phase.forecast { color: var(--accent-ink); }

.hud-fires { font-size: 0.85rem; }

.loading { position: absolute; inset: 0; display: grid; place-items: center; z-index: 1000; background: rgba(255, 255, 255, 0.6); border-radius: 12px; }

.controls { display: flex; align-items: center; gap: 12px; margin-top: 12px; }

.play {
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(180deg, #2C4596, var(--brand));
  color: #fff;
  font-size: 1rem;
  cursor: pointer;
  box-shadow: 0 8px 18px -8px rgba(34, 53, 122, 0.7);
}

.track { position: relative; flex: 1; padding-top: 14px; }

.track input { width: 100%; accent-color: var(--accent); }

.now-mark {
  position: absolute;
  top: -2px;
  transform: translateX(-50%);
  font-size: 0.7rem;
  font-weight: 800;
  color: #137333;
  text-transform: uppercase;
}

.small-btn { padding: 8px 14px; }

.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin-top: 10px; }

.legend span { display: inline-flex; align-items: center; gap: 6px; }

.streak { display: inline-block; width: 18px; height: 2px; background: rgba(34, 53, 122, 0.75); }

.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }

.dot.fire { background: #E8590C; }

.dot.smoke { background: linear-gradient(90deg, #F0A060, #8A8C96); }

.dot.city { background: #FFD60A; box-shadow: 0 0 0 2px #fff inset; }

.error { display: flex; gap: 8px; align-items: center; color: #B42318; margin: 12px 0; }

.map :deep(.radar-city) { padding: 1px 6px; font-size: 12px; }

.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

@media (max-width: 560px) { .map { height: 380px; } .hud-clock { font-size: 1.2rem; } }
</style>
