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
  return `Smoke from ${fires}${where} is likely to reach ${placeName} around ${when} — in about ${a.first_arrival_h} hours.`
}

export function localFiresNote(data) {
  const n = data?.local_fires
  if (!n) return ''
  return `${n} fire${n === 1 ? ' was' : 's were'} also detected within 30 km of the city in the last 36 hours.`
}
