// When the backend had to use its last good copy because a data provider was
// busy, payloads carry stale: { since, age_min }. One note covers them all.

function age(minutes) {
  if (minutes < 60) return `${Math.max(minutes, 1)} min`
  const hours = Math.round(minutes / 60)
  return `about ${hours} h`
}

export function staleNote(...payloads) {
  const ages = payloads.map((p) => p?.stale?.age_min).filter((m) => Number.isFinite(m))
  if (!ages.length) return ''
  return `A data provider is busy, so some of this is from ${age(Math.max(...ages))} ago.`
}
