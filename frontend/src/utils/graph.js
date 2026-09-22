// 关键词共现图谱的边视觉编码。
// 边的 value 是"共现论文数"：两个关键词在同一篇论文中共同出现的论文数量。
// 共现数呈长尾分布（中位数 ~19，最大 ~450），线性映射会让绝大多数边挤在
// 同一粗细，因此宽度和透明度都按平方根比例压缩后再归一化。

export const EDGE_MIN_WIDTH = 1
export const EDGE_MAX_WIDTH = 5
export const EDGE_MIN_OPACITY = 0.16
export const EDGE_MAX_OPACITY = 0.58
export const NODE_MIN_OPACITY = 0.5
export const NODE_MAX_OPACITY = 1
const NODE_COLOR_LOW = [8, 47, 73]
const NODE_COLOR_HIGH = [165, 243, 252]

// 图谱默认显示共现达到 30 篇的关系，在保持结构可读的同时保留更多边；
// 可用"显示全部关系"开关查看全量。
export const STRONG_EDGE_THRESHOLD = 30

export function edgeVisual(value, maxValue) {
  const numeric = Number(value)
  const max = Number(maxValue)
  if (!Number.isFinite(numeric) || !Number.isFinite(max) || max <= 0) {
    return { width: EDGE_MIN_WIDTH, opacity: EDGE_MIN_OPACITY }
  }
  const ratio = Math.sqrt(Math.max(numeric, 1) / max)
  return {
    width: EDGE_MIN_WIDTH + (EDGE_MAX_WIDTH - EDGE_MIN_WIDTH) * ratio,
    opacity: EDGE_MIN_OPACITY + (EDGE_MAX_OPACITY - EDGE_MIN_OPACITY) * ratio,
  }
}

export function nodeVisual(value, maxValue) {
  const numeric = Number(value)
  const max = Number(maxValue)
  if (!Number.isFinite(numeric) || !Number.isFinite(max) || max <= 0) {
    return { opacity: NODE_MIN_OPACITY }
  }
  const ratio = Math.sqrt(Math.max(numeric, 1) / max)
  return {
    opacity: NODE_MIN_OPACITY + (NODE_MAX_OPACITY - NODE_MIN_OPACITY) * ratio,
  }
}

export function nodeColor(value, maxValue) {
  const numeric = Number(value)
  const max = Number(maxValue)
  if (!Number.isFinite(numeric) || !Number.isFinite(max) || max <= 0) {
    return rgbToHex(NODE_COLOR_LOW)
  }
  const ratio = Math.sqrt(Math.max(numeric, 1) / max)
  const color = NODE_COLOR_LOW.map((channel, index) => (
    Math.round(channel + (NODE_COLOR_HIGH[index] - channel) * ratio)
  ))
  return rgbToHex(color)
}

function rgbToHex(channels) {
  return `#${channels.map((channel) => channel.toString(16).padStart(2, "0")).join("")}`
}
