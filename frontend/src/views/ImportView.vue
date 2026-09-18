<template>
  <AppShell>
    <div class="page-head">
      <div>
        <div class="eyebrow">INGESTION / IMPORT</div>
        <h1 class="page-title">论文导入工作站</h1>
        <p class="page-intro">通过标题检索或 CSV 批量导入构建可追溯的论文数据源；所有记录最终写入 SQLite。</p>
      </div>
      <router-link class="button secondary" to="/papers">返回论文库</router-link>
    </div>

    <div v-if="successMessage" class="success-box">{{ successMessage }}</div>
    <div class="import-grid">
      <section class="panel">
        <div class="panel-heading"><div><div class="eyebrow">SINGLE / LOOKUP</div><h2>单篇标题检索</h2></div><span class="mono dim">在线来源</span></div>
        <div class="panel-body">
          <form class="lookup-form" @submit.prevent="lookup">
            <label>论文标题
              <input v-model.trim="title" class="field" required placeholder="例如: Segment Anything" />
            </label>
            <button class="button" type="submit" :disabled="lookupLoading">{{ lookupLoading ? "检索中…" : "开始检索" }}</button>
          </form>
          <div v-if="lookupError" class="error-box">{{ lookupError }}</div>
          <div v-if="lookupPaper" class="review-card">
            <div class="result-meta"><span class="venue">{{ lookupPaper.conference }}</span><span>{{ lookupPaper.year }}</span><span>{{ lookupPaper.source || "online" }}</span></div>
            <h3>{{ lookupPaper.title }}</h3>
            <p class="result-authors">{{ lookupPaper.authors || "作者信息未提供" }}</p>
            <div class="keyword-list"><span v-for="keyword in lookupPaper.keywords" :key="keyword" class="keyword">{{ keyword }}</span></div>
            <p class="result-abstract">{{ lookupPaper.abstract || "在线来源未提供摘要。" }}</p>
            <a v-if="lookupPaper.source_url" class="source-link" :href="lookupPaper.source_url" target="_blank" rel="noreferrer">打开原文链接 ↗</a>
            <button class="button save-button" type="button" :disabled="saveLoading" @click="saveLookup">{{ saveLoading ? "保存中…" : "确认保存到 SQLite" }}</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-heading"><div><div class="eyebrow">BATCH / CSV</div><h2>批量导入论文</h2></div><span class="mono dim">UTF-8 CSV</span></div>
        <div class="panel-body">
          <p class="muted">每行一篇论文。必需字段为 <span class="mono">title</span>、<span class="mono">conference</span>、<span class="mono">year</span>；关键词可用逗号、分号或竖线分隔。</p>
          <label class="file-picker">选择 CSV 文件
            <input type="file" accept=".csv,text/csv" @change="selectFile" />
          </label>
          <div v-if="selectedFile" class="selected-file"><span class="mono">{{ selectedFile.name }}</span><span class="dim">{{ formatBytes(selectedFile.size) }}</span></div>
          <button class="button upload-button" type="button" :disabled="!selectedFile || importLoading" @click="uploadCsv">{{ importLoading ? "导入中…" : "开始批量导入" }}</button>
          <div class="csv-example">
            <div class="eyebrow">CSV HEADER</div>
            <code>title,conference,year,authors,abstract,keywords,source_url</code>
          </div>
          <div v-if="importError" class="error-box">{{ importError }}</div>
          <ImportResults :summary="importSummary" />
        </div>
      </section>
    </div>

    <section class="panel notes-panel">
      <div class="panel-heading"><div><div class="eyebrow">TRACEABILITY / NOTES</div><h2>导入口径</h2></div></div>
      <div class="panel-body note-grid">
        <div><strong>来源保留</strong><p>单篇检索记录保留在线来源和原文链接；手工录入与 CSV 记录保留对应 source 标记。</p></div>
        <div><strong>关键词可复现</strong><p>导入时优先使用提供的关键词；缺失时由后端根据标题和摘要执行确定性的 TF-IDF 提取。</p></div>
        <div><strong>重复保护</strong><p>同一会议、年份和规范化标题只允许一条记录，批量导入中的重复行会被标记为跳过。</p></div>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { ref } from "vue"

import { getErrorMessage, papersApi } from "../api"
import AppShell from "../components/AppShell.vue"
import ImportResults from "../components/ImportResults.vue"

const title = ref("")
const lookupPaper = ref(null)
const lookupLoading = ref(false)
const saveLoading = ref(false)
const lookupError = ref("")
const successMessage = ref("")
const selectedFile = ref(null)
const importLoading = ref(false)
const importSummary = ref(null)
const importError = ref("")

async function lookup() {
  lookupLoading.value = true
  lookupError.value = ""
  successMessage.value = ""
  lookupPaper.value = null
  try {
    const response = await papersApi.lookup(title.value)
    lookupPaper.value = response.data
  } catch (cause) {
    lookupError.value = getErrorMessage(cause, "在线检索失败，请检查后端检索源配置")
  } finally {
    lookupLoading.value = false
  }
}
async function saveLookup() {
  if (!lookupPaper.value) return
  saveLoading.value = true
  lookupError.value = ""
  try {
    await papersApi.create(lookupPaper.value)
    successMessage.value = "论文已保存到 SQLite，可以在论文库中继续编辑。"
    lookupPaper.value = null
  } catch (cause) {
    lookupError.value = getErrorMessage(cause, "论文保存失败")
  } finally {
    saveLoading.value = false
  }
}
function selectFile(event) {
  selectedFile.value = event.target.files?.[0] || null
  importSummary.value = null
  importError.value = ""
  successMessage.value = ""
}
async function uploadCsv() {
  if (!selectedFile.value) return
  importLoading.value = true
  importError.value = ""
  successMessage.value = ""
  try {
    const response = await papersApi.importCsv(selectedFile.value)
    importSummary.value = response.data
    successMessage.value = "批量导入处理完成，结果已按行展示。"
  } catch (cause) {
    importError.value = getErrorMessage(cause, "CSV 导入失败")
  } finally {
    importLoading.value = false
  }
}
function formatBytes(value) {
  if (!value) return "0 B"
  if (value < 1024) return value + " B"
  return (value / 1024).toFixed(1) + " KB"
}
</script>

<style scoped>
.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.import-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.panel-body > .muted { margin-top: 0; }
.lookup-form { display: flex; gap: 10px; align-items: end; }
.lookup-form label { display: grid; flex: 1; gap: 5px; color: var(--text-soft); font-size: 12px; }
.review-card { margin-top: 20px; padding: 16px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: rgba(7, 12, 22, .5); }
.review-card h3 { margin: 10px 0 5px; font: 600 20px/1.35 var(--serif); }
.result-authors, .result-abstract { color: var(--text-soft); }
.result-abstract { white-space: pre-wrap; }
.keyword-list { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.keyword { padding: 4px 7px; border: 1px solid rgba(34, 211, 238, .28); border-radius: 3px; color: var(--cyan); font: 11px var(--mono); }
.source-link { display: inline-block; color: var(--cyan); }
.save-button { width: 100%; margin-top: 18px; }
.file-picker { display: grid; gap: 8px; padding: 20px; border: 1px dashed var(--line-strong); border-radius: var(--radius-sm); color: var(--text-soft); text-align: center; }
.file-picker input { width: 100%; color: var(--text-soft); }
.selected-file { display: flex; justify-content: space-between; gap: 12px; margin-top: 12px; font-size: 12px; }
.upload-button { width: 100%; margin-top: 14px; }
.csv-example { display: grid; gap: 8px; margin-top: 20px; padding: 12px; border-left: 2px solid var(--cyan); background: rgba(34, 211, 238, .05); }
.csv-example code { overflow-x: auto; color: var(--text-soft); font: 11px var(--mono); white-space: nowrap; }
.success-box { margin-bottom: 18px; padding: 12px 15px; border: 1px solid rgba(52, 211, 153, .35); border-radius: var(--radius-sm); background: rgba(52, 211, 153, .08); color: var(--green); }
.notes-panel { margin-top: 18px; }
.note-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.note-grid strong { color: var(--cyan); font: 12px var(--mono); }
.note-grid p { margin: 8px 0 0; color: var(--text-soft); font-size: 13px; }
.error-box { margin-top: 14px; }
@media (max-width: 900px) { .import-grid, .note-grid { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .page-head { display: block; } .page-head .button { display: inline-flex; margin-top: 16px; } .lookup-form { display: grid; } }
</style>

