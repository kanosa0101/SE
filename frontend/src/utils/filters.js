// 热度单位是千分比（‰）：每 1000 篇论文中覆盖该关键词的论文数。
// 同一篇论文可携带多个关键词，因此各关键词覆盖率之和可超过 1000‰。
export function formatHeat(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? `${numeric.toFixed(1)}‰` : "—"
}

export function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return "—"
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(1)}%`
}

export function formatConferenceYear(conference, year) {
  return [conference, year].filter(Boolean).join(" · ") || "未标注来源"
}
