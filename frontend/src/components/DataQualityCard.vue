<template>
  <article class="panel quality-card" aria-labelledby="quality-heading">
    <div class="panel-heading">
      <div>
        <div class="eyebrow">DATA / QUALITY AUDIT</div>
        <h2 id="quality-heading">数据质量审计</h2>
        <p class="quality-intro">对当前 SQLite 样本的字段完整性、来源分布和会议年份覆盖进行透明检查。</p>
      </div>
      <button class="button secondary quality-retry-top" type="button" :disabled="loading" @click="load">刷新审计</button>
    </div>

    <div v-if="loading" class="loading-box">正在读取质量审计……</div>
    <div v-else-if="error" class="error-box" role="alert">
      {{ error }}
      <button class="button secondary retry" type="button" @click="load">重试</button>
    </div>
    <div v-else-if="isEmpty" class="empty-box">
      暂无可审计的论文数据。导入论文后可查看字段完整性、来源分布和会议年份覆盖。
    </div>
    <div v-else class="quality-content">
      <div class="quality-stats">
        <div class="quality-stat"><span>论文总量</span><strong>{{ audit.total }}</strong></div>
        <div class="quality-stat"><span>关键词覆盖</span><strong>{{ formatPercent(audit.keyword_coverage) }}</strong></div>
        <div class="quality-stat"><span>缺失摘要</span><strong>{{ audit.missing_fields.abstract || 0 }}</strong></div>
        <div class="quality-stat"><span>缺失作者</span><strong>{{ audit.missing_fields.authors || 0 }}</strong></div>
      </div>

      <div class="quality-sections">
        <section class="quality-section">
          <div class="section-label">字段缺失量</div>
          <div class="quality-list">
            <div v-for="row in fieldRows" :key="row.key" class="quality-row">
              <div class="quality-row-label"><span>{{ row.label }}</span><span class="mono">{{ row.count }} / {{ audit.total }}</span></div>
              <div class="quality-track"><span class="quality-fill missing" :style="{ width: barWidth(row.count) }"></span></div>
            </div>
          </div>
        </section>

        <section class="quality-section">
          <div class="section-label">来源分布</div>
          <div class="quality-list">
            <div v-for="row in sourceRows" :key="row.source" class="quality-row">
              <div class="quality-row-label"><span>{{ row.source }}</span><span class="mono">{{ row.papers }}</span></div>
              <div class="quality-track"><span class="quality-fill source" :style="{ width: barWidth(row.papers, maxSourceCount) }"></span></div>
            </div>
            <div v-if="!sourceRows.length" class="dim">暂无来源分布。</div>
          </div>
        </section>
      </div>

      <section class="quality-section matrix-section">
        <div class="section-label">会议 / 年份覆盖</div>
        <div v-if="matrixRows.length" class="matrix-wrap">
          <table class="matrix-table">
            <thead><tr><th>会议</th><th>年份</th><th>论文数</th></tr></thead>
            <tbody><tr v-for="row in matrixRows" :key="row.conference + '-' + row.year"><td>{{ row.conference }}</td><td>{{ row.year }}</td><td>{{ row.papers }}</td></tr></tbody>
          </table>
        </div>
        <div v-else class="dim">暂无会议年份覆盖。</div>
      </section>
    </div>
  </article>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"

import { getErrorMessage, statsApi } from "../api"

const audit = ref(null)
const loading = ref(false)
const error = ref("")
let requestSequence = 0

const fieldLabels = {
  abstract: "摘要",
  authors: "作者",
  source_url: "原文链接",
}
const fieldRows = computed(() => Object.entries(audit.value?.missing_fields || {}).map(([key, count]) => ({
  key,
  label: fieldLabels[key] || key,
  count,
})))
const sourceRows = computed(() => audit.value?.source_breakdown || [])
const matrixRows = computed(() => audit.value?.conference_year_matrix || [])
const maxSourceCount = computed(() => Math.max(1, ...sourceRows.value.map((row) => row.papers)))
const isEmpty = computed(() => !audit.value || audit.value.total === 0)

function formatPercent(value) {
  return Number(value || 0).toFixed(1) + "%"
}
function barWidth(value, denominator = audit.value?.total || 1) {
  return Math.min(100, Math.max(0, Number(value || 0) / denominator * 100)) + "%"
}
async function load() {
  const requestId = ++requestSequence
  loading.value = true
  error.value = ""
  try {
    const response = await statsApi.quality()
    if (requestId !== requestSequence) return
    audit.value = response.data
  } catch (cause) {
    if (requestId !== requestSequence) return
    error.value = getErrorMessage(cause, "质量审计暂时不可用")
  } finally {
    if (requestId === requestSequence) loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.quality-card { padding: 0; }
.quality-card .panel-heading { align-items: flex-start; }
.quality-intro { margin: 8px 0 0; color: var(--text-soft); font-size: 12px; }
.quality-content { padding: 0 22px 22px; }
.quality-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 22px; }
.quality-stat { display: grid; gap: 8px; padding: 14px; border: 1px solid var(--line); background: rgba(76, 215, 246, .04); }
.quality-stat span { color: var(--text-soft); font-size: 12px; }
.quality-stat strong { color: var(--cyan); font: 600 22px var(--mono); }
.quality-sections { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.quality-section { min-width: 0; }
.section-label { margin-bottom: 12px; color: var(--text-dim); font: 11px var(--mono); letter-spacing: .08em; text-transform: uppercase; }
.quality-list { display: grid; gap: 12px; }
.quality-row { display: grid; gap: 6px; }
.quality-row-label { display: flex; justify-content: space-between; gap: 12px; color: var(--text-soft); font-size: 12px; }
.quality-track { height: 5px; overflow: hidden; background: var(--surface-container-high); }
.quality-fill { display: block; height: 100%; min-width: 2px; }
.quality-fill.missing { background: var(--coral); }
.quality-fill.source { background: var(--green); }
.matrix-section { margin-top: 24px; }
.matrix-wrap { overflow-x: auto; }
.matrix-table { width: 100%; border-collapse: collapse; color: var(--text-soft); font-size: 12px; }
.matrix-table th, .matrix-table td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; }
.matrix-table th { color: var(--text-dim); font: 10px var(--mono); }
.matrix-table td:last-child { color: var(--cyan); font-family: var(--mono); }
.retry { margin-left: 8px; min-height: 30px; }
@media (max-width: 700px) { .quality-stats, .quality-sections { grid-template-columns: 1fr 1fr; } }
@media (max-width: 480px) { .quality-stats, .quality-sections { grid-template-columns: 1fr; } .quality-card .panel-heading { display: block; } .quality-retry-top { margin-top: 14px; } }
</style>
