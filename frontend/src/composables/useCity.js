// Shared state for the selected city, used by every dashboard section.
// Module-level refs make this a singleton: switching sections keeps the data.
import { computed, ref } from 'vue'
import { useAirData, useSchoolPlan, useSmokeForecast, useSmokeTrail } from './useAirData'
import { cityNow } from '../lib/aqi'

export const DEFAULT_PLACE = { name: 'New Delhi', region: 'Delhi', lat: 28.6139, lon: 77.209 }

const place = ref(DEFAULT_PLACE)
const schoolTimes = ref({}) // e.g. { assembly: '07:30' }; empty = server defaults
const airData = useAirData()
const school = useSchoolPlan()
const trail = useSmokeTrail()
const forecast = useSmokeForecast()

// Real time in the selected city, refreshed every minute.
const tick = ref(Date.now())
setInterval(() => { tick.value = Date.now() }, 60_000)

const now = computed(() => {
  const air = airData.air.value
  if (!air) return ''
  return cityNow(air.location.timezone, new Date(tick.value)) || air.current.time
})

let loadedFor = null

function loadAll(force = false) {
  const key = `${place.value.lat},${place.value.lon}`
  if (!force && key === loadedFor) return
  loadedFor = key
  airData.load(place.value)
  school.load(place.value, schoolTimes.value)
  trail.load(place.value)
  forecast.load(place.value)
}

function selectPlace(next) {
  place.value = next
  loadAll()
}

function changeSchoolTimes(times) {
  schoolTimes.value = { ...schoolTimes.value, ...times }
  school.load(place.value, schoolTimes.value)
}

export function useCity() {
  return {
    place, schoolTimes, now,
    air: airData.air, airLoading: airData.loading, airError: airData.error,
    reloadAir: () => airData.load(place.value),
    school, trail, forecast,
    loadAll, selectPlace, changeSchoolTimes,
  }
}
