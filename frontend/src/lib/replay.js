// Demo replay: a dated snapshot of real data (see backend data/replay/).
// Kept deliberately small — this is for demo reliability, not history browsing.
import { ref } from 'vue'

export const REPLAYS = {
  '2026-10-08': {
    label: '8 Oct 2026',
    capturedUtc: '2026-10-08T12:09:44Z',
    cities: [
      { name: 'New Delhi', region: 'Delhi', lat: 28.6139, lon: 77.209 },
      { name: 'Ludhiana', region: 'Punjab', lat: 30.912, lon: 75.8538 },
      { name: 'Chandigarh', region: 'Chandigarh', lat: 30.7363, lon: 76.7884 },
    ],
  },
}

// '' = live data; otherwise a key of REPLAYS.
export const replayDate = ref('')

// Which snapshots the backend actually has. The data isn't in the git repo
// (it's served from S3 when deployed), so a fresh clone may have none.
export const availableReplays = ref(null) // null = not checked yet
let checking = null

export function loadAvailableReplays() {
  checking ||= fetch('/api/replays')
    .then((res) => (res.ok ? res.json() : { dates: [] }))
    .then((body) => { availableReplays.value = (body.dates || []).map((d) => d.date) })
    .catch(() => { availableReplays.value = [] })
  return checking
}

// No default parameter on purpose: replayInfo(undefined) must mean "none",
// not "the current one" (a default param silently did that and broke exit).
export function replayInfo(date) {
  return (typeof date === 'string' && REPLAYS[date]) || null
}

export const currentReplay = () => replayInfo(replayDate.value)

export function isReplayCity(place, date) {
  const info = replayInfo(date)
  return !!info && info.cities.some((c) => Math.abs(c.lat - place.lat) <= 0.3 && Math.abs(c.lon - place.lon) <= 0.3)
}
