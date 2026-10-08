// Shared state for the selected city, used by every dashboard section.
// Module-level refs make this a singleton: switching sections keeps the data.
import { computed, ref } from 'vue'
import { useAirData, useSchoolPlan, useSmokeForecast, useSmokeTrail } from './useAirData'
import { cityNow } from '../lib/aqi'
import { currentReplay, replayDate } from '../lib/replay'

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
  // In a demo replay the clock is frozen at the capture time, so "today",
  // "tomorrow" and past school slots match the replayed data.
  const info = currentReplay()
  const instant = info ? new Date(info.capturedUtc) : new Date(tick.value)
  return cityNow(air.location?.timezone, instant) || air.current?.time || ''
})

let loadedFor = null

// The replay date is part of the request, so live and replay data for the same
// city never get mixed up.
const request = () => ({ ...place.value, replay: replayDate.value || undefined })

function loadAll(force = false) {
  const key = `${place.value.lat},${place.value.lon},${replayDate.value}`
  if (!force && key === loadedFor) return
  loadedFor = key
  airData.load(request())
  school.load(request(), schoolTimes.value)
  trail.load(request())
  forecast.load(request())
}

function selectPlace(next) {
  place.value = next
  loadAll()
}

function changeSchoolTimes(times) {
  schoolTimes.value = { ...schoolTimes.value, ...times }
  school.load(request(), schoolTimes.value)
}

export function useCity() {
  return {
    place, schoolTimes, now,
    air: airData.air, airLoading: airData.loading, airError: airData.error,
    reloadAir: () => airData.load(request()),
    request, replayDate,
    school, trail, forecast,
    loadAll, selectPlace, changeSchoolTimes,
  }
}
