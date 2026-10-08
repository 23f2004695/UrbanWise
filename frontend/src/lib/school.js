// Colour and symbol for each School Mode decision. The symbol keeps the
// meaning clear without relying on colour alone.
export const DECISION_STYLES = {
  go: { symbol: '✓', bg: '#00B050', fg: '#0B2914' },
  caution: { symbol: '!', bg: '#FFD60A', fg: '#2B2300' },
  limit: { symbol: '!', bg: '#FF9900', fg: '#2B1700' },
  cancel: { symbol: '✕', bg: '#E00000', fg: '#FFFFFF' },
  unknown: { symbol: '?', bg: '#8A94A6', fg: '#17213A' },
}

export function decisionStyle(decision) {
  return DECISION_STYLES[decision] || DECISION_STYLES.unknown
}

// One-line summary for a day, driven by its strictest slot.
const SEVERITY = ['unknown', 'go', 'caution', 'limit', 'cancel']

export function daySummary(slots) {
  const worst = slots.reduce(
    (acc, s) => (SEVERITY.indexOf(s.decision) > SEVERITY.indexOf(acc) ? s.decision : acc),
    'unknown',
  )
  return {
    unknown: 'No forecast available',
    go: 'All outdoor activities can go ahead',
    caution: 'Outdoor activities OK — watch children with asthma',
    limit: 'Limit outdoor activities',
    cancel: 'Cancel outdoor activities',
  }[worst]
}

// A slot has passed if its hour is earlier than the current hour today.
export function isPast(date, time, nowIso) {
  return `${date}T${time}` < `${nowIso.slice(0, 13)}:00`
}
