<template>
  <AppShell>
    <div class="page-head">
      <div>
        <div class="eyebrow">OBSERVATORY / OVERVIEW</div>
        <h1 class="page-title">研究热点总览</h1>
        <p class="page-intro">从论文元数据、关键词关系和会议年度热度中，快速定位计算机视觉研究的变化方向。</p>
      </div>
      <div class="status-line"><span class="status-dot" />统计口径：论文覆盖率</div>
    </div>

    <div class="filter-bar panel">
      <label>会议 <select v-model="filters.conference" class="select"><option value="">全部顶会</option><option value="CVPR">CVPR</option><option value="ICCV">ICCV</option><option value="ECCV">ECCV</option></select></label>
      <label>起始年 <input v-model.number="filters.year_from" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
      <label>结束年 <input v-model.number="filters.year_to" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
      <button class="button secondary" type="button" @click="resetFilters">重置筛选</button>
    </div>

    <div v-if="loading" class="loading-box">正在读取观测样本……</div>
    <div v-else-if="error" class="error-box">{{ error }} <button class="button secondary retry" type="button" @click="load">重试</button></div>
    <template v-else>
      <section class="metrics-grid">
        <MetricCard label="样本论文" :value="formatNumber(summary.total_papers)" caption="当前筛选范围" />
        <MetricCard label="覆盖会议" :value="summary.conference_count" caption="CVPR / ICCV / ECCV" tone="amber" />
        <MetricCard label="年份跨度" :value="yearRange" caption="来自当前数据库" tone="green" />
        <MetricCard label="热门关键词" :value="topics[0]?.keyword || '—'" :caption="topics[0] ? formatHeat(topics[0].heat) + ' 覆盖率' : '暂无统计'" tone="coral" />
      </section>

      <section class="dashboard-grid">
        <article class="panel topics-panel">
          <div class="panel-heading"><div><div class="eyebrow">RANK / TOPIC COVERAGE</div><h2>Top 10 热门关键词</h2></div><span class="mono dim">最多 10 项</span></div>
          <div class="panel-body topic-list">
            <button v-for="(topic, index) in topics" :key="topic.keyword" class="topic-row" type="button" @click="openTopic(topic.keyword)">
              <span class="rank">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="topic-name">{{ topic.keyword }}</span>
              <span class="topic-count">{{ topic.papers }} 篇</span>
              <span class="topic-heat">{{ formatHeat(topic.heat) }}</span>
            </button>
            <div v-if="!topics.length" class="empty-box compact">当前筛选范围没有关键词统计。</div>
          </div>
        </article>

        <article class="panel graph-panel">
          <div class="panel-heading"><div><div class="eyebrow">NETWORK / CO-OCCURRENCE</div><h2>关键词关系图谱</h2></div><span class="mono dim">点击节点查看论文</span></div>
          <div class="panel-body"><KeywordGraph :graph="graph" @select="openTopic" /></div>
        </article>
      </section>
    </template>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRouter } from "vue-router"

import { getErrorMessage, statsApi } from "../api"
import AppShell from "../components/AppShell.vue"
import KeywordGraph from "../components/KeywordGraph.vue"
import MetricCard from "../components/MetricCard.vue"
import { formatHeat } from "../utils/filters"

const router = useRouter()
const filters = reactive({ conference: "", year_from: "", year_to: "" })
const summary = ref({ total_papers: 0, conference_count: 0, year_from: null, year_to: null })
const topics = ref([])
const graph = ref({ nodes: [], links: [] })
const loading = ref(true)
const error = ref("")

const yearRange = computed(() => {
  if (!summary.value.year_from || !summary.value.year_to) return "—"
  return String(summary.value.year_from) + " — " + String(summary.value.year_to)
})
function formatNumber(value) { return new Intl.NumberFormat("zh-CN").format(Number(value || 0)) }
function queryParams() {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "" && value !== null && value !== undefined))
}
async function load() {
  loading.value = true
  error.value = ""
  try {
    const params = queryParams()
    const [overviewResponse, topicsResponse, graphResponse] = await Promise.all([
      statsApi.overview(params),
      statsApi.topics(params),
      statsApi.graph(params),
    ])
    summary.value = overviewResponse.data
    topics.value = topicsResponse.data
    graph.value = graphResponse.data
  } catch (cause) {
    error.value = getErrorMessage(cause, "统计接口暂时不可用")
  } finally {
    loading.value = false
  }
}
function resetFilters() {
  Object.assign(filters, { conference: "", year_from: "", year_to: "" })
}
function openTopic(keyword) {
  router.push({ name: "papers", query: { keyword } })
}
watch(() => [filters.conference, filters.year_from, filters.year_to], load)
onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.filter-bar { display: flex; align-items: end; gap: 12px; padding: 14px 16px; margin-bottom: 18px; }
.filter-bar label { display: grid; gap: 5px; color: var(--text-soft); font-size: 12px; }
.filter-bar .select { min-width: 150px; }
.year-field { width: 110px; }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
.dashboard-grid { display: grid; grid-template-columns: minmax(300px, 0.8fr) minmax(420px, 1.2fr); gap: 18px; }
.topic-list { display: grid; gap: 6px; }
.topic-row { display: grid; grid-template-columns: 36px 1fr auto auto; align-items: center; gap: 10px; padding: 12px 10px; border: 1px solid transparent; border-radius: var(--radius-sm); background: rgba(7, 12, 22, 0.45); color: var(--text); text-align: left; }
.topic-row:hover { border-color: var(--line-strong); background: rgba(34, 211, 238, 0.07); }
.rank { color: var(--cyan); font: 12px var(--mono); }
.topic-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topic-count, .topic-heat { color: var(--text-soft); font: 11px var(--mono); }
.topic-heat { color: var(--amber); }
.compact { padding: 16px; }
.retry { margin-left: 8px; min-height: 32px; }
@media (max-width: 1100px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); } .dashboard-grid { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .page-head { display: block; } .filter-bar { flex-wrap: wrap; } .metrics-grid { grid-template-columns: 1fr; } }
</style>

