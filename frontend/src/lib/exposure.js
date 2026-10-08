// Personal exposure estimate. Kept client-side so the result updates instantly
// as the user moves the sliders.

// Breathing rate relative to resting: more effort → more air (and PM) inhaled.
export const ACTIVITIES = {
  resting: { label: 'Sitting / waiting', factor: 1 },
  walking: { label: 'Walking', factor: 2 },
  sports: { label: 'Sports / running', factor: 3.5 },
}

// Sensitivity doesn't change how much is inhaled, only how much harm it does.
export const PEOPLE = {
  adult: { label: 'Healthy adult', factor: 1 },
  child: { label: 'Child', factor: 1.5 },
  sensitive: { label: 'Asthma, heart condition or elderly', factor: 2 },
}

// Berkeley Earth rule of thumb: 22 µg/m³ PM2.5 breathed for 24 h ≈ 1 cigarette.
const PM25_PER_CIGARETTE_DAY = 22

export function cigarettes(pm25, hours, activity) {
  const factor = ACTIVITIES[activity]?.factor ?? 1
  return (Math.max(pm25, 0) * hours * factor) / (24 * PM25_PER_CIGARETTE_DAY)
}

const LEVELS = [
  { max: 0.25, level: 'low', label: 'Low', advice: 'Fine to go ahead.' },
  { max: 1, level: 'moderate', label: 'Moderate', advice: 'OK for a short time. Take it easy and keep it brief.' },
  { max: 3, level: 'high', label: 'High', advice: 'Shorten it, slow down, or wear a well-fitted N95 mask.' },
  { max: Infinity, level: 'very-high', label: 'Very high', advice: 'Avoid if you can. Move indoors or pick a cleaner hour.' },
]

export function exposure({ pm25, hours, activity, person }) {
  const cigs = cigarettes(pm25, hours, activity)
  const weighted = cigs * (PEOPLE[person]?.factor ?? 1)
  const band = LEVELS.find((l) => weighted < l.max)
  return { cigarettes: cigs, weighted, ...band }
}

// Percentage saved by going at a cleaner hour; null when not worth mentioning.
export function savingPercent(nowPm25, betterPm25) {
  if (!(nowPm25 > 0) || betterPm25 == null) return null
  const saved = Math.round((1 - betterPm25 / nowPm25) * 100)
  return saved >= 15 ? saved : null
}

export function formatCigarettes(n) {
  if (n < 0.1) return 'less than 0.1'
  if (n < 1) return n.toFixed(1)
  return n < 10 ? n.toFixed(1).replace(/\.0$/, '') : String(Math.round(n))
}

export function formatDuration(hours) {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  if (!h) return `${m} min`
  return m ? `${h} h ${m} min` : `${h} h`
}
