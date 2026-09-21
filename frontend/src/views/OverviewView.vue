<template>
  <AppShell :record-count="summary.total_papers">
    <div class="page-head">
      <div>
        <div class="eyebrow">OBSERVATORY / OVERVIEW</div>
        <h1 class="page-title">研究热点总览</h1>
        <p class="page-intro">从论文元数据、关键词关系和会议年度热度中，快速定位计算机视觉研究的变化方向。</p>
      </div>
      <div class="status-line"><span class="status-dot" />统计口径：论文覆盖率</div>
    </div>

    <div class="filter-bar panel">
      <label>会议 <select :value="conference" class="select" @change="setConference($event.target.value)"><option value="">全部顶会</option><option value="CVPR">CVPR</option><option value="ICCV">ICCV</option><option value="ECCV">ECCV</option></select></label>
      <div class="year-group">
        <label>起始年 <input v-model.number="filters.year_from" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
        <label>结束年 <input v-model.number="filters.year_to" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" /></label>
      </div>
      <button class="button secondary" type="button" @click="resetFilters">重置筛选</button>
    </div>

    <div v-if="loading" class="loading-box">正在读取观测样本……</div>
    <div v-else-if="error" class="error-box">{{ error }} <button class="button secondary retry" type="button" @click="load">重试</button></div>
    <template v-else>
      <section class="metrics-grid">
        <MetricCard label="样本论文" :value="formatNumber(summary.total_papers)" caption="当前筛选范围" />
        <MetricCard label="覆盖会议" :value="summary.conference_count" caption="CVPR / ICCV / ECCV" tone="amber" />
        <MetricCard label="年份跨度" :value="yearRange" caption="来自当前数据库" tone="green" />
        <MetricCard label="热门研究方向" :value="topics[0]?.keyword || '—'" :caption="topics[0] ? formatHeat(topics[0].heat) + ' 覆盖率' : '暂无统计'" tone="coral" />
      </section>

      <section class="dashboard-grid">
        <article class="panel topics-panel">
          <div class="panel-heading"><div><div class="eyebrow">RANK / TOPIC COVERAGE</div><h2>Top 10 热门研究方向</h2></div><span class="mono dim">最多 10 项</span></div>
          <p class="topic-note">关键词按词元映射到研究领域后，以领域覆盖论文数（并集去重）降序排列；image、model 等泛化载体词不参与排名。覆盖率（‰）= 覆盖论文数 / 当前范围论文总数 × 1000；同一篇论文可属于多个领域，因此各领域覆盖率之和可超过 1000‰。</p>
          <div class="panel-body topic-list">
            <button v-for="(topic, index) in topics" :key="topic.keyword" class="topic-row" type="button" :aria-label="`了解更多：${topic.keyword}`" @click="selectTopic(topic.keyword, 'area')">
              <span class="rank">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="topic-name">{{ topic.keyword }}</span>
              <span class="topic-count">{{ topic.papers }} 篇</span>
              <span class="topic-heat">{{ formatHeat(topic.heat) }}</span>
            </button>
            <div v-if="!topics.length" class="empty-box compact">当前筛选范围没有关键词统计。</div>
          </div>
        </article>

        <article class="panel graph-panel">
          <div class="panel-heading"><div><div class="eyebrow">NETWORK / CO-OCCURRENCE</div><h2>关键词关系图谱</h2></div><span class="mono dim">点击节点查看详情</span></div>
          <div class="panel-body"><KeywordGraph :graph="graph" @select="selectTopic" /></div>
        </article>
      </section>
    </template>

    <TopicInspectorDrawer :keyword="selectedTopic?.keyword || ''" :scope="selectedTopic?.scope || 'keyword'" :open="Boolean(selectedTopic)" @close="closeInspector" @select-related="selectTopic" @view-papers="viewTopicPapers" />
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { getErrorMessage, statsApi } from "../api"
import AppShell from "../components/AppShell.vue"
import KeywordGraph from "../components/KeywordGraph.vue"
import MetricCard from "../components/MetricCard.vue"
import TopicInspectorDrawer from "../components/TopicInspectorDrawer.vue"
import { formatHeat } from "../utils/filters"

const router = useRouter()
const route = useRoute()
const filters = reactive({ year_from: "", year_to: "" })
const summary = ref({ total_papers: null, conference_count: 0, year_from: null, year_to: null })
const topics = ref([])
const graph = ref({ nodes: [], links: [] })
const selectedTopic = ref(null)
const loading = ref(true)
const error = ref("")
const loadRequestId = ref(0)

const yearRange = computed(() => {
  if (!summary.value.year_from || !summary.value.year_to) return "—"
  return String(summary.value.year_from) + " — " + String(summary.value.year_to)
})
function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "—"
  return new Intl.NumberFormat("zh-CN").format(Number(value))
}
function queryParams() {
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "" && value !== null && value !== undefined))
  if (conference.value) params.conference = conference.value
  return params
}
const conference = computed(() => typeof route.query.conference === "string" ? route.query.conference.toUpperCase() : "")
async function setConference(value) {
  const query = { ...route.query }
  if (value) query.conference = value
  else delete query.conference
  await router.replace({ query })
}
async function load() {
  const requestId = ++loadRequestId.value
  loading.value = true
  error.value = ""
  try {
    const params = queryParams()
    const [overviewResponse, topicsResponse, graphResponse] = await Promise.all([
      statsApi.overview(params),
      statsApi.topics(params),
      statsApi.graph(params),
    ])
    if (requestId !== loadRequestId.value) return
    summary.value = overviewResponse.data
    topics.value = topicsResponse.data
    graph.value = graphResponse.data
  } catch (cause) {
    if (requestId !== loadRequestId.value) return
    summary.value = { ...summary.value, total_papers: null }
    error.value = getErrorMessage(cause, "统计接口暂时不可用")
  } finally {
    if (requestId === loadRequestId.value) loading.value = false
  }
}
function resetFilters() {
  Object.assign(filters, { year_from: "", year_to: "" })
  setConference("")
}
function selectTopic(keyword, scope = "keyword") {
  if (keyword) selectedTopic.value = { keyword, scope }
}
function closeInspector() {
  selectedTopic.value = null
}
function viewTopicPapers(keyword, scope = "keyword") {
  const query = { ...route.query, keyword }
  if (scope === "area") query.keyword_scope = "area"
  else delete query.keyword_scope
  for (const [name, value] of Object.entries(filters)) {
    if (value !== "" && value !== null && value !== undefined) query[name] = value
  }
  router.push({ name: "papers", query })
  closeInspector()
}
watch(() => [route.query.conference, filters.year_from, filters.year_to], load)
onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.filter-bar { display: flex; align-items: end; gap: 12px; padding: 14px 16px; margin-bottom: 18px; }
.filter-bar label { display: grid; gap: 5px; color: var(--text-soft); font-size: 12px; }
.filter-bar .select { min-width: 150px; }
.year-group { display: flex; align-items: end; gap: 12px; }
.year-field { width: 110px; }
.topic-note { margin: -6px 18px 10px; color: var(--text-dim); font-size: 11px; line-height: 1.7; }
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


