<template>
  <div>
    <div class="chart-toolbar">
      <button class="button secondary" type="button" @click="togglePlayback">{{ playing ? "暂停" : "播放" }}</button>
      <button class="button secondary" type="button" @click="resetPlayback">重置</button>
      <span class="chart-status">{{ activeYear || "等待数据" }} · {{ speed }}x</span>
      <label class="speed-select">速度 <select v-model="speed"><option :value="1">1x</option><option :value="1.5">1.5x</option><option :value="2">2x</option></select></label>
    </div>
    <div ref="chartElement" class="trend-canvas" aria-label="关键词热度趋势图" />
  </div>
</template>

<script setup>
import * as echarts from "echarts"
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

const props = defineProps({
  payload: { type: Object, default: () => ({ years: [], series: [] }) },
  conference: { type: String, default: "" },
})
const chartElement = ref(null)
const playing = ref(false)
const speed = ref(1)
const activeIndex = ref(0)
let chart
let timer

const activeYear = computed(() => props.payload.years?.[activeIndex.value] || "")

function valueFor(series, year) {
  const values = (series.data || []).filter((row) => row.year === year && (!props.conference || row.conference === props.conference))
  if (!values.length) return null
  return values.reduce((sum, item) => sum + Number(item.heat || 0), 0) / values.length
}

function renderChart() {
  if (!chart) return
  const years = props.payload.years || []
  const visibleYears = years.slice(0, Math.max(1, activeIndex.value + 1))
  chart.setOption({
    color: ["#22d3ee", "#fbbf24", "#34d399", "#fb7185", "#a78bfa"],
    tooltip: { trigger: "axis" },
    legend: { top: 4, textStyle: { color: "#a5b4c6" } },
    grid: { left: 48, right: 22, top: 48, bottom: 32 },
    xAxis: { type: "category", data: visibleYears, axisLabel: { color: "#94a3b8" }, axisLine: { lineStyle: { color: "#334155" } } },
    yAxis: { type: "value", name: "热度 / 1000篇", nameTextStyle: { color: "#64748b" }, axisLabel: { color: "#94a3b8" }, splitLine: { lineStyle: { color: "rgba(148,163,184,.12)" } } },
    series: (props.payload.series || []).slice(0, 8).map((series) => ({
      name: series.keyword,
      type: "line",
      smooth: true,
      connectNulls: true,
      data: visibleYears.map((year) => valueFor(series, year)),
    })),
  }, true)
}

function stopTimer() {
  if (timer) window.clearInterval(timer)
  timer = undefined
  playing.value = false
}
function startTimer() {
  stopTimer()
  if ((props.payload.years || []).length < 2) return
  playing.value = true
  timer = window.setInterval(() => {
    if (activeIndex.value >= props.payload.years.length - 1) {
      stopTimer()
      return
    }
    activeIndex.value += 1
    renderChart()
  }, 1200 / Number(speed.value))
}
function togglePlayback() {
  if (playing.value) stopTimer()
  else startTimer()
}
function resetPlayback() {
  stopTimer()
  activeIndex.value = 0
  renderChart()
}

onMounted(() => {
  chart = echarts.init(chartElement.value)
  renderChart()
})
watch(() => [props.payload, props.conference], () => { activeIndex.value = 0; renderChart() }, { deep: true })
watch(speed, () => { if (playing.value) startTimer() })
onBeforeUnmount(() => { stopTimer(); chart?.dispose() })
</script>

<style scoped>
.chart-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.chart-toolbar .button { min-height: 32px; padding: 0 10px; font-size: 12px; }
.chart-status { margin-left: auto; color: var(--cyan); font: 12px var(--mono); }
.speed-select { color: var(--text-soft); font-size: 12px; }
.speed-select select { margin-left: 4px; border: 1px solid var(--line); background: var(--ink-900); color: var(--text); }
.trend-canvas { width: 100%; min-height: 430px; }
</style>

