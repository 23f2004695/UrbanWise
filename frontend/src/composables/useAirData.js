import { ref } from 'vue'

async function getJson(url) {
  const res = await fetch(url)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`)
  return body
}

// Loads one endpoint at a time and ignores responses for superseded requests
// (e.g. the user switched city before the previous city finished loading).
function useLatest(fetcher) {
  const data = ref(null)
  const loading = ref(false)
  const error = ref('')
  let latest = 0
  let lastArgs = null

  async function load(...args) {
    const request = ++latest
    // Asking for something different (e.g. another city): drop the old data so
    // it can never be shown under the new name, even if this request fails.
    const argsKey = JSON.stringify(args)
    if (argsKey !== lastArgs) data.value = null
    lastArgs = argsKey
    loading.value = true
    error.value = ''
    try {
      const result = await fetcher(...args)
      if (request === latest) data.value = result
    } catch (err) {
      if (request === latest) error.value = err.message
    } finally {
      if (request === latest) loading.value = false
    }
  }

  return { data, loading, error, load }
}

// `place.replay` (a date) asks for the demo-replay snapshot instead of live data.
function query(place, extra = {}) {
  const params = new URLSearchParams({ lat: place.lat, lon: place.lon, ...extra })
  if (place.replay) params.set('replay', place.replay)
  return params
}

export function useAirData() {
  const { data: air, ...rest } = useLatest(
    (place) => getJson(`/api/air?${query(place)}`),
  )
  return { air, ...rest }
}

export function useSchoolPlan() {
  const { data, ...rest } = useLatest((place, times) =>
    getJson(`/api/school?${query(place, times)}`).then((d) => d.days))
  return { days: data, ...rest }
}

export function useSmokeTrail() {
  return useLatest((place) => getJson(`/api/smoke-trail?${query(place)}`))
}

export function useSmokeForecast() {
  return useLatest((place) => getJson(`/api/smoke-forecast?${query(place)}`))
}

export function searchPlaces(query) {
  return getJson(`/api/geocode?q=${encodeURIComponent(query)}`).then((d) => d.results)
}
