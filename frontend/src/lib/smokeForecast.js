import { formatInZone } from './aqi'

function joinNames(names) {
  if (names.length <= 1) return names.join('')
  return `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
}

/** Plain-language alert for the Incoming Smoke Alert. */
export function forecastHeadline(data, placeName, timeZone) {
  if (!data) return ''
  const a = data.alert
  if (!a.incoming) {
    return `No smoke from current fires is expected to reach ${placeName} in the next 48 hours.`
  }
  const when = formatInZone(a.first_arrival_time, timeZone)
  const where = a.districts.length ? ` near ${joinNames(a.districts.slice(0, 3))}` : ''
  const fires = `${a.fires} fire${a.fires === 1 ? '' : 's'}`
  return `Smoke from ${fires}${where} may reach ${placeName} around ${when} (in about ${a.first_arrival_h} h).`
}

export function localFiresNote(data) {
  const n = data?.local_fires
  if (!n) return ''
  return `${n} fire${n === 1 ? ' was' : 's were'} also detected within 30 km of the city in the last 36 hours.`
}

/**
 * Whether a second weather model (GFS) agrees with the alert.
 * Returns null when there was no second model to compare with.
 */
export function modelsCheck(data) {
  const m = data?.alert?.models
  if (!m || m.agree == null) return null
  const s = m.second
  if (m.agree) {
    const sentence = !data.alert.incoming
      ? 'A second weather model (GFS) agrees.'
      : s.first_arrival_h === data.alert.first_arrival_h
        ? 'A second weather model (GFS) brings this smoke at about the same time.'
        : `A second weather model (GFS) also brings this smoke, in about ${s.first_arrival_h} h.`
    return { agree: true, chip: '2 models agree', sentence }
  }
  const sentence = data.alert.incoming
    ? "A second weather model (GFS) doesn't bring this smoke here, so treat it as uncertain."
    : `A second weather model (GFS) shows smoke from ${s.fires} fire${s.fires === 1 ? '' : 's'}`
      + `${s.districts.length ? ` near ${joinNames(s.districts.slice(0, 3))}` : ''}`
      + ` may arrive in about ${s.first_arrival_h} h, so keep an eye on it.`
  return { agree: false, chip: 'Models disagree', sentence }
}
