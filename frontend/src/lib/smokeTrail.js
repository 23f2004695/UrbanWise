// Plain-language headline for the Smoke Trail summary card.
export function trailHeadline(summary, placeName) {
  if (!summary) return ''
  if (summary.stagnant) {
    return `Your air has barely moved in the last ${summary.hours_traced} hours.`
  }
  const count = summary.fire_count
  if (count === 0) {
    return `Your air travelled about ${summary.trail_km} km in ${summary.hours_traced} hours without passing any detected fires.`
  }
  const fires = `${count} fire${count === 1 ? '' : 's'}`
  const names = summary.top_districts.slice(0, 3).map((d) => d.district)
  // Only say "near X" outright when the named districts account for every fire.
  const allNamed = summary.top_districts.length <= 3 && !summary.other_fires
  let where = ''
  if (names.length) {
    where = allNamed ? ` near ${joinNames(names)}` : `, including some near ${joinNames(names)},`
  }
  return `Your air likely passed ${fires}${where} in the last ${summary.hours_traced} hours.`
}

export function trailDetail(summary) {
  if (!summary) return ''
  if (summary.stagnant) {
    return 'Local sources such as traffic, construction and waste burning are likely trapping pollution.'
  }
  return `It travelled about ${summary.trail_km} km to reach you.`
}

function joinNames(names) {
  if (names.length <= 1) return names.join('')
  return `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`
}

// Marker radius in pixels: grows with fire intensity but stays readable.
export function fireRadius(frp) {
  return Math.min(4 + Math.sqrt(Math.max(frp, 0)) * 1.6, 14)
}
