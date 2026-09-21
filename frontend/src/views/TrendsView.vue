<template>
  <AppShell>
    <div class="page-head">
      <div><div class="eyebrow">SPECTRUM / TRENDS</div><h1 class="page-title">热度趋势洞察</h1><p class="page-intro">用统一的论文覆盖率口径，比较三大会议中研究方向的年度变化。</p></div>
      <div class="status-line"><span class="status-dot" />支持播放、暂停与速度调整</div>
    </div>
    <div class="filter-bar panel">
      <label>会议 <select v-model="conference" class="select"><option value="">全部会议</option><option value="CVPR">CVPR</option><option value="ICCV">ICCV</option><option value="ECCV">ECCV</option></select></label>
      <label>起始年 <input v-model.number="yearFrom" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
      <label>结束年 <input v-model.number="yearTo" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
      <button class="button secondary" type="button" @click="reset">重置筛选</button>
    </div>
    <div v-if="loading" class="loading-box">正在生成年度热度序列……</div>
    <div v-else-if="error" class="error-box">{{ error }} <button class="button secondary retry" type="button" @click="load">重试</button></div>
    <template v-else>
      <article class="panel chart-panel"><div class="panel-heading"><div><div class="eyebrow">HEAT / TIME SERIES</div><h2>研究方向年度热度轨迹</h2></div><span class="mono dim">单位：每千篇论文覆盖数</span></div><div class="panel-body"><TrendChart :payload="payload" :conference="conference" /></div></article>
      <EvolutionPanel />
      <article class="panel table-panel"><div class="panel-heading"><div><div class="eyebrow">METHOD / DEFINITION</div><h2>如何阅读这张图</h2></div></div><div class="panel-body method-grid"><div><strong>热度</strong><p>某研究方向在会议/年份论文中的覆盖率乘以 1000，减少不同年份样本量差异。</p></div><div><strong>联动</strong><p>切换会议或年份后，图表重新从 SQLite 统计接口读取数据，不使用页面硬编码数字。</p></div><div><strong>边界</strong><p>研究方向由原始关键词或 TF-IDF 结果按固定词元映射得到，来源在论文详情中单独标记。</p></div></div></article>
    </template>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { getErrorMessage, statsApi } from "../api"
import AppShell from "../components/AppShell.vue"
import EvolutionPanel from "../components/EvolutionPanel.vue"
import TrendChart from "../components/TrendChart.vue"

const route = useRoute()
const router = useRouter()
const yearFrom = ref("")
const yearTo = ref("")
const payload = ref({ years: [], series: [] })
const loading = ref(true)
const error = ref("")
const loadRequestId = ref(0)

const conference = computed({
  get: () => typeof route.query.conference === "string" ? route.query.conference.toUpperCase() : "",
  set: (value) => setConference(value),
})

async function setConference(value) {
  const query = { ...route.query }
  if (value) query.conference = value
  else delete query.conference
  await router.replace({ query })
}

function params() {
  return Object.fromEntries(Object.entries({ conference: conference.value, year_from: yearFrom.value, year_to: yearTo.value }).filter(([, value]) => value !== "" && value !== null))
}
async function load() {
  const requestId = ++loadRequestId.value
  loading.value = true
  error.value = ""
  try {
    const response = await statsApi.trends(params())
    if (requestId !== loadRequestId.value) return
    payload.value = response.data
  } catch (cause) {
    if (requestId !== loadRequestId.value) return
    error.value = getErrorMessage(cause, "趋势接口暂时不可用")
  } finally {
    if (requestId === loadRequestId.value) loading.value = false
  }
}
function reset() { setConference(""); yearFrom.value = ""; yearTo.value = "" }
watch(() => [route.query.conference, yearFrom.value, yearTo.value], load)
onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.filter-bar { display: flex; align-items: end; gap: 12px; padding: 14px 16px; margin-bottom: 18px; }
.filter-bar label { display: grid; gap: 5px; color: var(--text-soft); font-size: 12px; }
.filter-bar .select { min-width: 150px; }
.year-field { width: 110px; }
.chart-panel { margin-bottom: 18px; }
.table-panel p { margin: 8px 0 0; color: var(--text-soft); }
.method-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.method-grid strong { color: var(--cyan); font: 12px var(--mono); }
.retry { margin-left: 8px; min-height: 32px; }
@media (max-width: 700px) { .page-head { display: block; } .filter-bar { flex-wrap: wrap; } .method-grid { grid-template-columns: 1fr; } }
</style>
