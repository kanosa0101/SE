export function formatHeat(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)}%` : "—"
}

export function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "—"
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(1)}%`
}

export function formatConferenceYear(conference, year) {
  return [conference, year].filter(Boolean).join(" · ") || "未标注来源"
}
