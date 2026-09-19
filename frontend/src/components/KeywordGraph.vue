<template>
  <div>
    <div class="chart-toolbar">
      <button class="button secondary" type="button" :aria-pressed="strongOnly" @click="strongOnly = !strongOnly">
        {{ strongOnly ? "显示全部关系" : "仅看强关系" }}
      </button>
      <span class="legend-note">
        连线粗细与深浅 ∝ 共现论文数（当前 {{ edgeRange.min }}—{{ edgeRange.max }} 篇，平方根映射）
      </span>
    </div>
    <div ref="chartElement" class="graph-canvas" aria-label="关键词共现关系图" />
  </div>
</template>

<script setup>
import * as echarts from "../utils/echarts"
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

import { edgeVisual, STRONG_EDGE_THRESHOLD } from "../utils/graph"

const props = defineProps({
  graph: { type: Object, default: () => ({ nodes: [], links: [] }) },
})
const emit = defineEmits(["select"])
const chartElement = ref(null)
const strongOnly = ref(false)
let chart
let observer

const edgeRange = computed(() => {
  const values = (props.graph.links || []).map((link) => Number(link.value) || 0)
  return { min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 0 }
})

// ECharts force 布局在高边密度下会震荡发散，这里用固定迭代的
// Fruchterman-Reingold 预计算坐标，保证布局确定、紧凑且可复现。
function computeLayout(nodes, links, width, height, iterations = 260) {
  const index = new Map(nodes.map((node, i) => [node.name, i]))
  const pos = nodes.map((_, i) => {
    const angle = (i / Math.max(nodes.length, 1)) * Math.PI * 2
    return { x: width / 2 + Math.cos(angle) * width * 0.32, y: height / 2 + Math.sin(angle) * height * 0.32 }
  })
  const pairs = links
    .map((link) => [index.get(link.source), index.get(link.target)])
    .filter((pair) => pair[0] !== undefined && pair[1] !== undefined && pair[0] !== pair[1])
  const idealEdge = Math.max(34, Math.sqrt((width * height) / Math.max(nodes.length, 1)) * 0.55)
  const k = idealEdge * 1.4
  for (let step = 0; step < iterations; step++) {
    const fx = new Array(nodes.length).fill(0)
    const fy = new Array(nodes.length).fill(0)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = pos[i].x - pos[j].x
        const dy = pos[i].y - pos[j].y
        const d2 = dx * dx + dy * dy || 1
        const d = Math.sqrt(d2)
        const force = (k * k) / d2
        fx[i] += (dx / d) * force
        fy[i] += (dy / d) * force
        fx[j] -= (dx / d) * force
        fy[j] -= (dy / d) * force
      }
    }
    for (const [a, b] of pairs) {
      const dx = pos[a].x - pos[b].x
      const dy = pos[a].y - pos[b].y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (d * d) / idealEdge
      fx[a] -= (dx / d) * force
      fy[a] -= (dy / d) * force
      fx[b] += (dx / d) * force
      fy[b] += (dy / d) * force
    }
    const temperature = 14 * (1 - step / iterations) + 1
    for (let i = 0; i < nodes.length; i++) {
      const dx = fx[i]
      const dy = fy[i]
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const move = Math.min(d, temperature)
      pos[i].x = Math.max(34, Math.min(width - 34, pos[i].x + (dx / d) * move))
      pos[i].y = Math.max(28, Math.min(height - 28, pos[i].y + (dy / d) * move))
    }
  }
  return pos
}

function renderGraph() {
  if (!chart) return
  const width = chartElement.value?.clientWidth || 640
  const height = chartElement.value?.clientHeight || 420
  const nodes = (props.graph.nodes || []).map((node) => ({
    ...node,
    symbolSize: Math.max(9, Math.min(30, 6 + Number(node.value || 0) * 0.09)),
    itemStyle: { color: node.name.includes("diffusion") ? "#fbbf24" : "#22d3ee" },
  }))
  const maxValue = edgeRange.value.max
  const links = (props.graph.links || [])
    .filter((link) => !strongOnly.value || Number(link.value) >= STRONG_EDGE_THRESHOLD)
    .map((link) => ({
      ...link,
      lineStyle: { ...edgeVisual(link.value, maxValue) },
    }))
  const pos = computeLayout(nodes, links, width, height)
  nodes.forEach((node, i) => {
    node.x = pos[i].x
    node.y = pos[i].y
  })
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        if (params.dataType === "edge") {
          return `${params.data.source} ⇄ ${params.data.target}<br/>共现论文数：${params.data.value}`
        }
        return `${params.data.name}<br/>覆盖论文数：${params.data.value}`
      },
    },
    series: [{
      type: "graph",
      layout: "none",
      data: nodes,
      links,
      roam: true,
      draggable: true,
      label: { show: true, color: "#dbeafe", fontSize: 10 },
      lineStyle: { color: "#64748b", opacity: 0.3, width: 1, curveness: 0 },
    }],
  }, true)
}

onMounted(async () => {
  await nextTick()
  chart = echarts.init(chartElement.value)
  chart.on("click", (params) => {
    if (params.data?.name) emit("select", params.data.name)
  })
  observer = new ResizeObserver(() => {
    chart?.resize()
    renderGraph()
  })
  observer.observe(chartElement.value)
  renderGraph()
})
watch([() => props.graph, strongOnly], renderGraph, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>
.chart-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.chart-toolbar .button { min-height: 30px; padding: 0 10px; font-size: 12px; }
.legend-note { color: var(--text-dim); font-size: 11px; line-height: 1.6; }
.graph-canvas { width: 100%; min-height: 420px; }
</style>
