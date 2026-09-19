<template>
  <div ref="chartElement" class="graph-canvas" aria-label="关键词共现关系图" />
</template>

<script setup>
import * as echarts from "../utils/echarts"
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"

const props = defineProps({
  graph: { type: Object, default: () => ({ nodes: [], links: [] }) },
})
const emit = defineEmits(["select"])
const chartElement = ref(null)
let chart
let observer

function renderGraph() {
  if (!chart) return
  const nodes = (props.graph.nodes || []).map((node) => ({
    ...node,
    symbolSize: Math.max(18, Math.min(62, 14 + Number(node.value || 0) * 8)),
    itemStyle: { color: node.name.includes("diffusion") ? "#fbbf24" : "#22d3ee" },
  }))
  chart.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item" },
    series: [{
      type: "graph",
      layout: "force",
      data: nodes,
      links: props.graph.links || [],
      roam: true,
      draggable: true,
      label: { show: true, color: "#dbeafe", fontSize: 11 },
      lineStyle: { color: "#64748b", opacity: 0.45, width: 1 },
      force: { repulsion: 130, edgeLength: [60, 150] },
    }],
  }, true)
}

onMounted(async () => {
  await nextTick()
  chart = echarts.init(chartElement.value)
  chart.on("click", (params) => {
    if (params.data?.name) emit("select", params.data.name)
  })
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartElement.value)
  renderGraph()
})
watch(() => props.graph, renderGraph, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>
.graph-canvas { width: 100%; min-height: 420px; }
</style>

