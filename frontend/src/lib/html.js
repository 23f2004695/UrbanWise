// Leaflet tooltips/divIcons treat strings as HTML. Anything that isn't our own
// fixed markup must go through escapeHtml — e.g. the city name, which can come
// from the URL (?city=…) and was a reflected XSS before this existed.
const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ENTITIES[ch])
}
