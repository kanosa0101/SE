<template>
  <div>
    <div class="chart-toolbar">
      <button class="button secondary" type="button" @click="togglePlayback">{{ playing ? "暂停" : "播放" }}</button>
      <button class="button secondary" type="button" @click="resetPlayback">重置</button>
      <span class="chart-status">{{ activeYear || "等待数据" }} · {{ speed }}x</span>
      <label class="speed-select">速度 <select v-model="speed"><option :value="1">1x</option><option :value="1.5">1.5x</option><option :value="2">2x</option></select></label>
    </div>
    <div ref="chartElement" class="trend-canvas" aria-label="研究方向热度趋势图" />
  </div>
</template>

<script setup>
import * as echarts from "../utils/echarts"
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

const props = defineProps({
  payload: { type: Object, default: () => ({ years: [], series: [] }) },
  conference: { type: String, default: "" },
  keyword: { type: String, default: "" },
})
const chartElement = ref(null)
const playing = ref(false)
const speed = ref(1)
const activeIndex = ref(0)
let chart
let timer

const activeYear = computed(() => props.payload.years?.[activeIndex.value] || "")

function renderChart() {
  if (!chart) return
  const years = props.payload.years || []
  const visibleYears = years.slice(0, Math.max(1, activeIndex.value + 1))
  const selected = (props.payload.series || []).find((series) => series.keyword === props.keyword)
    || (props.payload.series || [])[0]
  const conferences = props.conference ? [props.conference] : ["CVPR", "ICCV", "ECCV"]
  const colors = { CVPR: "#4cd7f6", ICCV: "#ffb95f", ECCV: "#4edea3" }
  const lineTypes = { CVPR: "solid", ICCV: "dashed", ECCV: "dotted" }
  chart.setOption({
    color: conferences.map((venue) => colors[venue]),
    tooltip: { trigger: "axis" },
    legend: { type: "scroll", top: 4, left: 82, right: 8, textStyle: { color: "#bcc9cd" } },
    grid: { left: 74, right: 22, top: 60, bottom: 32, containLabel: true },
    xAxis: { type: "category", data: visibleYears, axisLabel: { color: "#869397" }, axisLine: { lineStyle: { color: "#3d494c" } } },
    yAxis: { type: "value", name: "热度 / 1000篇", nameLocation: "middle", nameGap: 42, nameRotate: 90, nameTextStyle: { color: "#869397" }, axisLabel: { color: "#869397" }, splitLine: { lineStyle: { color: "rgba(134,147,151,.12)" } } },
    series: selected ? conferences.map((venue) => ({
      name: venue,
      type: "line",
      smooth: true,
      connectNulls: false,
      lineStyle: { type: lineTypes[venue], width: 2.5 },
      itemStyle: { color: colors[venue] },
      data: visibleYears.map((year) => {
        const value = (selected.data || []).find((row) => row.year === year && row.conference === venue)
        return value ? Number(value.heat) : null
      }),
    })) : [],
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
watch(() => [props.payload, props.conference, props.keyword], () => { activeIndex.value = 0; renderChart() }, { deep: true })
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

