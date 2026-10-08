<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AirNowCard from '../components/AirNowCard.vue'
import AssistantPanel from '../components/AssistantPanel.vue'
import CircularDialog from '../components/CircularDialog.vue'
import CitySearch from '../components/CitySearch.vue'
import ExposureCalculator from '../components/ExposureCalculator.vue'
import ForecastChart from '../components/ForecastChart.vue'
import Icon3D from '../components/Icon3D.vue'
import SchoolModePanel from '../components/SchoolModePanel.vue'
import SmokeAlertBanner from '../components/SmokeAlertBanner.vue'
import SmokeForecastMap from '../components/SmokeForecastMap.vue'
import SmokeRadar from '../components/SmokeRadar.vue'
import SmokeTrailMap from '../components/SmokeTrailMap.vue'
import VentilationCard from '../components/VentilationCard.vue'
import { useCity } from '../composables/useCity'
import { formatHour, grapStage, relativeHour } from '../lib/aqi'
import { daySummary } from '../lib/school'
import { trailHeadline } from '../lib/smokeTrail'
import { SECTIONS } from '../router'

const route = useRoute()
const router = useRouter()
const city = useCity()
const { place, air, school, trail, forecast, now } = city

const section = computed(() => route.params.section || 'overview')
const current = computed(() => SECTIONS.find((s) => s.id === section.value))

// The city lives in the URL (?city=&lat=&lon=) so links can be shared.
function placeFromQuery(q) {
  // Number('') is 0, so require non-empty values and real coordinates.
  if (!q.city || !q.lat || !q.lon) return null
  const lat = Number(q.lat)
  const lon = Number(q.lon)
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
  return { name: String(q.city), region: q.region ? String(q.region) : '', lat, lon }
}

const query = computed(() => ({
  city: place.value.name, region: place.value.region || undefined,
  lat: place.value.lat, lon: place.value.lon,
}))

function selectPlace(next) {
  city.selectPlace(next)
  // Keep other query params (e.g. ?view=radar) when the city changes.
  router.replace({ params: route.params, query: { ...route.query, ...query.value } })
}

onMounted(() => {
  const fromUrl = placeFromQuery(route.query)
  if (fromUrl) city.selectPlace(fromUrl)
  else city.loadAll()
})

watch(() => route.query, (q) => {
  const fromUrl = placeFromQuery(q)
  if (fromUrl && (fromUrl.lat !== place.value.lat || fromUrl.lon !== place.value.lon)) city.selectPlace(fromUrl)
})

// ---------- overview tiles ----------
const tomorrow = computed(() => school.days.value?.[1])
const tiles = computed(() => {
  const a = air.value
  if (!a) return []
  const grap = grapStage(a.current.aqi) // current AQI is a 24 h average, the basis GRAP uses
  const t = trail.data.value?.summary
  const pm = a.current.pm25_now ?? a.current.pm25
  const best = a.best_hour
  const bestWhen = best ? relativeHour(best.time, now.value || a.current.time) : ''
  return [
    { icon: 'cloud', label: 'PM2.5 this hour', value: pm != null ? `${Math.round(pm)}` : '—', unit: 'µg/m³' },
    { icon: 'sun_behind_cloud', label: 'Best time outside', value: best ? formatHour(best.time) : '—',
      unit: best ? `${bestWhen.startsWith('tomorrow') ? 'tomorrow' : 'today'} · AQI ${best.aqi}` : '' },
    { icon: 'face_with_medical_mask', label: 'GRAP stage', value: grap ? `Stage ${grap}` : 'None', unit: grap ? 'restrictions apply' : 'below Stage I' },
    { icon: 'fire', label: 'Fires on air\'s path', value: t ? String(t.fire_count) : '…', unit: t ? `in ${t.hours_traced} h` : 'tracing' },
  ]
})

const circular = ref({ open: false, date: '' })

const timeZone = computed(() => air.value?.location?.timezone || 'Asia/Kolkata')

// Smoke section views: where it came from (past) / what's coming (forecast).
const SMOKE_VIEWS = [
  { id: 'past', label: 'Where it came from', sub: 'past 48 h' },
  { id: 'coming', label: "What's coming", sub: 'next 48 h' },
  { id: 'radar', label: 'Smoke Radar', sub: 'time-lapse' },
]
const smokeView = computed(() => {
  const v = route.query.view
  if (SMOKE_VIEWS.some((x) => x.id === v)) return v
  return forecast.data.value?.alert.incoming ? 'coming' : 'past'
})
const smokeLink = (view) => ({ name: 'dashboard', params: { section: 'smoke' }, query: { ...query.value, view } })

// CPCB bands → School Mode decisions (mirrors backend services/advisory.py).
const RULES = [
  ['0–100', '—', 'Go', '#00B050'],
  ['101–200', '—', 'Go with care', '#FFD60A'],
  ['201–300', 'I', 'Limit', '#FF9900'],
  ['301–400', 'II', 'Cancel', '#FF0000'],
  ['401+', 'III / IV', 'Cancel · indoor only', '#C00000'],
]
const linkTo = (id) => ({ name: 'dashboard', params: { section: id === 'overview' ? '' : id }, query: query.value })
</script>

<template>
  <div class="shell">
    <!-- Sidebar (desktop) -->
    <aside class="sidebar" aria-label="Sections">
      <RouterLink to="/" class="brand">
        <img src="/favicon.svg" alt="" width="34" height="34" />
        <span><strong>UrbanWise</strong><small>Bad-air-day assistant</small></span>
      </RouterLink>
      <nav>
        <RouterLink
          v-for="s in SECTIONS"
          :key="s.id"
          :to="linkTo(s.id)"
          class="nav-item"
          :class="{ active: section === s.id }"
          :aria-current="section === s.id ? 'page' : undefined"
        >
          <Icon3D :name="s.icon" :size="30" :float="section === s.id" />
          <span>{{ s.label }}</span>
        </RouterLink>
      </nav>
      <RouterLink to="/" class="home-link small">← Back to home</RouterLink>
    </aside>

    <div class="main">
      <header class="topbar">
        <RouterLink to="/" class="brand mobile-brand" aria-label="UrbanWise home">
          <img src="/favicon.svg" alt="" width="30" height="30" />
        </RouterLink>
        <div class="title">
          <p class="eyebrow">{{ current?.label }}</p>
          <h1>Air in {{ place.name }}</h1>
        </div>
        <CitySearch @select="selectPlace" />
      </header>

      <div v-if="city.airError.value" class="card error" role="alert">
        <strong>Couldn't load air quality for {{ place.name }}.</strong>
        <span>{{ city.airError.value }}</span>
        <button type="button" class="btn btn-ghost" @click="city.reloadAir()">Try again</button>
      </div>

      <Transition name="section" mode="out-in">
        <!-- OVERVIEW -->
        <div v-if="section === 'overview'" key="overview" class="grid">
          <SmokeAlertBanner :data="forecast.data.value" :place="place" :time-zone="timeZone" :link="smokeLink('coming')" />
          <AirNowCard :place="place" :air="air" :loading="city.airLoading.value" :now="now" />

          <div v-if="tiles.length" class="tiles">
            <div v-for="(t, i) in tiles" :key="t.label" class="card tile">
              <Icon3D :name="t.icon" :size="40" :delay="i * 0.7" />
              <div>
                <p class="tile-label">{{ t.label }}</p>
                <p class="tile-value">{{ t.value }}</p>
                <p class="tile-unit">{{ t.unit }}</p>
              </div>
            </div>
          </div>

          <ForecastChart v-if="air" :forecast="air.forecast" />

          <div class="pair">
            <RouterLink :to="linkTo('school')" class="card teaser">
              <Icon3D name="school" :size="56" />
              <div>
                <p class="eyebrow">School Mode · tomorrow</p>
                <p class="teaser-text">{{ tomorrow ? daySummary(tomorrow.slots) : 'Loading…' }}</p>
                <span class="teaser-link">See activity by activity →</span>
              </div>
            </RouterLink>
            <RouterLink :to="linkTo('smoke')" class="card teaser">
              <Icon3D name="fire" :size="56" :delay="1.3" />
              <div>
                <p class="eyebrow">Smoke Trail</p>
                <p class="teaser-text">{{ trail.data.value ? trailHeadline(trail.data.value.summary, place.name) : 'Tracing the air backwards…' }}</p>
                <span class="teaser-link">Watch the trail on the map →</span>
              </div>
            </RouterLink>
          </div>
        </div>

        <!-- SMOKE TRAIL -->
        <div v-else-if="section === 'smoke'" key="smoke" class="grid">
          <nav class="views" aria-label="Smoke view">
            <!-- custom: the router ignores ?view= when marking links active -->
            <RouterLink
              v-for="v in SMOKE_VIEWS"
              :key="v.id"
              v-slot="{ href, navigate }"
              :to="smokeLink(v.id)"
              custom
              replace
            >
              <a
                :href="href"
                :class="{ active: smokeView === v.id }"
                :aria-current="smokeView === v.id ? 'page' : undefined"
                @click="navigate"
              >{{ v.label }} <small>{{ v.sub }}</small></a>
            </RouterLink>
          </nav>
          <SmokeRadar v-if="smokeView === 'radar'" :place="place" :time-zone="timeZone" />
          <SmokeForecastMap
            v-else-if="smokeView === 'coming'"
            :place="place"
            :data="forecast.data.value"
            :loading="forecast.loading.value"
            :error="forecast.error.value"
            :time-zone="timeZone"
            @retry="forecast.load(place)"
          />
          <SmokeTrailMap
            v-else
            :place="place"
            :data="trail.data.value"
            :loading="trail.loading.value"
            :error="trail.error.value"
            @retry="trail.load(place)"
          />
        </div>

        <!-- SCHOOL -->
        <div v-else-if="section === 'school'" key="school" class="grid">
          <SmokeAlertBanner
            v-if="forecast.data.value?.alert.incoming"
            :data="forecast.data.value" :place="place" :time-zone="timeZone" :link="smokeLink('coming')"
          />
          <div class="split">
          <SchoolModePanel
            :days="school.days.value"
            :loading="school.loading.value"
            :error="school.error.value"
            :now="now"
            @change-times="city.changeSchoolTimes"
            @retry="school.load(place, city.schoolTimes.value)"
            @write-circular="(date) => (circular = { open: true, date })"
          />
          <aside class="card side">
            <div class="card-head">
              <Icon3D name="chart_increasing" :size="40" />
              <h2>How School Mode decides</h2>
            </div>
            <p class="muted small">Each activity is checked against the forecast AQI for its own hour, on India's CPCB scale.</p>
            <table class="rules">
              <thead><tr><th>AQI</th><th>GRAP</th><th>Decision</th></tr></thead>
              <tbody>
                <tr v-for="r in RULES" :key="r[0]">
                  <td><span class="sw" :style="{ background: r[3] }"></span>{{ r[0] }}</td>
                  <td>{{ r[1] }}</td>
                  <td>{{ r[2] }}</td>
                </tr>
              </tbody>
            </table>
            <p class="muted small">GRAP is the Graded Response Action Plan used in Delhi-NCR.</p>
          </aside>
          </div>
        </div>

        <!-- HEALTH -->
        <div v-else-if="section === 'health'" key="health" class="grid">
          <ExposureCalculator :air="air" :now="now" />
          <VentilationCard v-if="air" :air="air" :now="now" />
        </div>

        <!-- ASK -->
        <div v-else key="ask" class="split">
          <AssistantPanel :place="place" :times="city.schoolTimes.value" class="tall" />
          <aside class="card side">
            <div class="card-head">
              <Icon3D name="satellite" :size="40" />
              <h2>What it knows</h2>
            </div>
            <p class="muted small">Answers come only from {{ place.name }}'s live data:</p>
            <ul class="knows">
              <li><Icon3D name="cloud" :size="26" :float="false" /> Air now and the 48-hour forecast</li>
              <li><Icon3D name="school" :size="26" :float="false" /> School Mode for today and tomorrow</li>
              <li><Icon3D name="fire" :size="26" :float="false" /> The Smoke Trail and fires on its path</li>
              <li><Icon3D name="lungs" :size="26" :float="false" /> Exposure rule of thumb (cigarettes)</li>
            </ul>
            <p class="muted small">Tap 🎙 to ask by voice in English, हिंदी or ਪੰਜਾਬੀ, and 🔊 to hear the answer. Not medical advice.</p>
          </aside>
        </div>
      </Transition>
    </div>

    <!-- Bottom tabs (phones) -->
    <nav class="tabbar" aria-label="Sections">
      <RouterLink
        v-for="s in SECTIONS"
        :key="s.id"
        :to="linkTo(s.id)"
        :class="{ active: section === s.id }"
        :aria-current="section === s.id ? 'page' : undefined"
      >
        <Icon3D :name="s.icon" :size="26" :float="false" />
        <span>{{ s.short || s.label }}</span>
      </RouterLink>
    </nav>

    <CircularDialog
      :open="circular.open"
      :date="circular.date"
      :place="place"
      :times="city.schoolTimes.value"
      @close="circular.open = false"
    />
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  min-height: 100vh;
}

/* ---------- sidebar ---------- */
.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 22px;
  height: 100vh;
  padding: 22px 16px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(12px);
  border-right: 1px solid var(--border);
}

.brand { display: flex; align-items: center; gap: 10px; color: inherit; text-decoration: none; }

.brand span { display: flex; flex-direction: column; line-height: 1.2; }

.brand strong { color: var(--brand); font-size: 1.15rem; }

.brand small { color: var(--muted); font-size: 0.78rem; }

nav { display: grid; gap: 6px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  border-radius: 14px;
  color: var(--text);
  text-decoration: none;
  font-weight: 600;
  transition: background 0.2s ease, transform 0.2s ease;
}

.nav-item:hover { background: var(--surface-2); transform: translateX(3px); }

.nav-item.active {
  background: linear-gradient(135deg, #E8EEFF, #FFF1E6);
  color: var(--brand);
  box-shadow: inset 0 0 0 1px #D6E0FA;
}

.home-link { margin-top: auto; color: var(--muted); text-decoration: none; }

.home-link:hover { color: var(--brand); }

/* ---------- main ---------- */
.main {
  display: grid;
  align-content: start;
  gap: 18px;
  max-width: 1120px;
  width: 100%;
  margin: 0 auto;
  padding: 22px 24px 48px;
}

.topbar {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px 24px;
}

.title h1 { margin: 0; font-size: clamp(1.4rem, 2.6vw, 1.9rem); }

.eyebrow {
  margin: 0 0 2px;
  color: var(--accent-ink);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; }

.split {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.side p { margin: 10px 0; }

.side h2 { font-size: 1.02rem; }

.rules { width: 100%; border-collapse: collapse; font-size: 0.9rem; }

.rules th { text-align: left; color: var(--muted); font-weight: 600; padding: 6px 4px; border-bottom: 1px solid var(--border); }

.rules td { padding: 8px 4px; border-bottom: 1px solid var(--border); }

.sw { display: inline-block; width: 10px; height: 10px; margin-right: 8px; border-radius: 3px; }

.knows { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; font-size: 0.92rem; }

.knows li { display: flex; align-items: center; gap: 10px; }

.views {
  display: flex;
  gap: 4px;
  padding: 4px;
  width: fit-content;
  max-width: 100%;
  overflow-x: auto;        /* three tabs don't fit a phone; scroll them, not the page */
  scrollbar-width: none;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.views a {
  padding: 8px 14px;
  border-radius: 10px;
  color: var(--muted);
  font-weight: 650;
  text-decoration: none;
  white-space: nowrap;
}

.views a small { font-weight: 500; opacity: 0.8; }

.views a.active { background: linear-gradient(135deg, #E8EEFF, #FFF1E6); color: var(--brand); }

.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.tile { display: flex; align-items: center; gap: 12px; padding: 16px; }

.tile p { margin: 0; }

.tile-label { color: var(--muted); font-size: 0.82rem; }

.tile-value { font-size: 1.35rem; font-weight: 800; color: var(--brand); }

.tile-unit { color: var(--muted); font-size: 0.78rem; }

.pair { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }

.teaser {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  color: inherit;
  text-decoration: none;
}

.teaser p { margin: 0 0 6px; }

.teaser-text { font-weight: 650; font-size: 1.02rem; }

.teaser-link { color: var(--brand); font-weight: 600; font-size: 0.9rem; }

.tall :deep(.messages) { min-height: 360px; max-height: 520px; }

.error { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; border-color: #E5484D; }

.error button { margin-left: auto; }

/* ---------- bottom tab bar (phones) ---------- */
.tabbar { display: none; }

.mobile-brand { display: none; }

@media (max-width: 1000px) {
  .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 860px) {
  .shell { grid-template-columns: minmax(0, 1fr); }
  .sidebar { display: none; }
  .mobile-brand { display: flex; }
  .topbar .title { flex: 1; }
  .main { padding: 16px 16px calc(110px + env(safe-area-inset-bottom)); }
  .pair, .split { grid-template-columns: minmax(0, 1fr); }
  .views { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; }
  .views a { text-align: center; white-space: normal; padding: 8px 6px; }
  .views a small { display: none; }
  /* Keep the message box above the tab bar without scrolling. */
  .tall :deep(.messages) { min-height: 180px; max-height: 50vh; }

  .tabbar {
    position: fixed;
    z-index: 1000;
    left: 10px;
    right: 10px;
    bottom: calc(10px + env(safe-area-inset-bottom));
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    padding: 6px;
    border: 1px solid var(--border);
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 30px -10px rgba(23, 33, 58, 0.35);
  }

  .tabbar a {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 2px;
    border-radius: 14px;
    color: var(--muted);
    text-decoration: none;
    font-size: 0.7rem;
    font-weight: 600;
  }

  .tabbar a.active { background: var(--surface-2); color: var(--brand); }

  .tabbar a.active :deep(.icon3d) { animation: pop 0.4s ease; }
}

@keyframes pop {
  0% { transform: scale(0.8); }
  60% { transform: scale(1.15); }
  100% { transform: scale(1); }
}

@media (max-width: 480px) {
  .tiles { grid-template-columns: minmax(0, 1fr); }
}
</style>
