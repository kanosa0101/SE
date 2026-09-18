<template>
  <AppShell>
    <div class="page-head">
      <div>
        <div class="eyebrow">CATALOG / PAPERS</div>
        <h1 class="page-title">论文库</h1>
        <p class="page-intro">管理已入库的 CVPR、ICCV 和 ECCV 论文，并沿着关键词追踪研究主题。</p>
      </div>
      <div class="page-actions">
        <router-link class="button secondary" to="/import">导入工作站</router-link>
        <button class="button" type="button" @click="openCreate">新建论文</button>
      </div>
    </div>

    <form class="search-panel panel" @submit.prevent="search">
      <label class="search-field">关键词或标题
        <input v-model.trim="filters.q" class="field" placeholder="输入论文标题、作者或关键词" />
      </label>
      <label>会议
        <select v-model="filters.conference" class="select">
          <option value="">全部会议</option>
          <option value="CVPR">CVPR</option>
          <option value="ICCV">ICCV</option>
          <option value="ECCV">ECCV</option>
        </select>
      </label>
      <label>年份
        <input v-model.number="filters.year" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" />
      </label>
      <label>起始年
        <input v-model.number="filters.year_from" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" />
      </label>
      <label>结束年
        <input v-model.number="filters.year_to" class="field year-field" type="number" min="1990" max="2100" placeholder="不限" />
      </label>
      <label>精确关键词
        <input v-model.trim="filters.keyword" class="field" placeholder="可选" />
      </label>
      <div class="search-actions">
        <button class="button" type="submit">检索</button>
        <button class="button secondary" type="button" @click="reset">重置</button>
      </div>
    </form>

    <div v-if="error" class="error-box">{{ error }} <button class="button secondary retry" type="button" @click="load">重试</button></div>
    <div v-else-if="loading" class="loading-box">正在读取论文记录……</div>
    <template v-else>
      <div class="result-bar">
        <span class="mono dim">本地数据库 {{ total }} 条记录</span>
        <span v-if="searched && filters.q && !items.length" class="dim">本地未找到匹配项，可发起在线检索</span>
        <div class="export-actions">
          <span v-if="exportError" class="export-error">{{ exportError }}</span>
          <button class="button secondary export-csv" type="button" :disabled="exportLoading" @click="downloadExport('csv')">{{ exportLoading ? "导出中…" : "导出 CSV" }}</button>
          <button class="button secondary export-bibtex" type="button" :disabled="exportLoading" @click="downloadExport('bibtex')">{{ exportLoading ? "导出中…" : "导出 BibTeX" }}</button>
        </div>
      </div>
      <section class="panel">
        <PaperTable :items="items" @detail="openDetail" @edit="openEdit" @delete="removePaper" />
        <div v-if="total > pageSize" class="pagination">
          <button class="button secondary" type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <span class="mono dim">第 {{ page }} / {{ totalPages }} 页</span>
          <button class="button secondary" type="button" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
        </div>
      </section>
    </template>

    <section v-if="searched && filters.q && !loading && !items.length" class="lookup-prompt panel">
      <div>
        <div class="eyebrow">REMOTE LOOKUP / FALLBACK</div>
        <h2>本地没有这篇论文</h2>
        <p>可以调用已配置的在线来源进行标题检索；检索结果需要确认后才会写入本地数据库。</p>
      </div>
      <button class="button" type="button" :disabled="lookupLoading" @click="lookupOnline">{{ lookupLoading ? "检索中…" : "在线检索" }}</button>
    </section>

    <section v-if="lookupError" class="error-box lookup-error">{{ lookupError }}</section>
    <section v-if="lookupPaper" class="lookup-result panel">
      <div class="panel-heading">
        <div><div class="eyebrow">REMOTE RESULT / REVIEW</div><h2>{{ lookupPaper.title }}</h2></div>
        <button class="icon-button" type="button" aria-label="关闭在线结果" @click="clearLookup">×</button>
      </div>
      <div class="panel-body">
        <div class="result-meta"><span class="venue">{{ lookupPaper.conference }}</span><span>{{ lookupPaper.year }}</span><span>{{ lookupPaper.source || "online" }}</span></div>
        <p class="result-authors">{{ lookupPaper.authors || "作者信息未提供" }}</p>
        <div class="keyword-list"><span v-for="keyword in lookupPaper.keywords" :key="keyword" class="keyword">{{ keyword }}</span></div>
        <p class="result-abstract">{{ lookupPaper.abstract || "在线来源未提供摘要。" }}</p>
        <div class="form-actions"><button class="button secondary" type="button" @click="clearLookup">放弃</button><button class="button" type="button" :disabled="saveLookupLoading" @click="saveLookup">{{ saveLookupLoading ? "入库中…" : "确认保存到本地" }}</button></div>
      </div>
    </section>

    <teleport to="body">
      <div v-if="formVisible" class="modal-backdrop" @click.self="closeForm">
        <section class="modal panel">
          <div class="panel-heading"><div><div class="eyebrow">{{ editingPaper ? "EDIT / PAPER" : "CREATE / PAPER" }}</div><h2>{{ editingPaper ? "编辑论文" : "新建论文" }}</h2></div><button class="icon-button" type="button" aria-label="关闭" @click="closeForm">×</button></div>
          <PaperForm :paper="editingPaper" :loading="saveLoading" @save="savePaper" @cancel="closeForm" />
        </section>
      </div>
      <div v-if="detailPaper" class="modal-backdrop" @click.self="detailPaper = null">
        <section class="modal panel detail-modal">
          <div class="panel-heading"><div><div class="eyebrow">PAPER / DETAIL</div><h2>论文详情</h2></div><button class="icon-button" type="button" aria-label="关闭" @click="detailPaper = null">×</button></div>
          <div class="panel-body detail-body">
            <h3>{{ detailPaper.title }}</h3>
            <div class="result-meta"><span class="venue">{{ detailPaper.conference }}</span><span>{{ detailPaper.year }}</span><span>{{ detailPaper.source }}</span></div>
            <p class="result-authors">{{ detailPaper.authors || "作者信息未提供" }}</p>
            <div class="keyword-list"><span v-for="keyword in detailPaper.keywords" :key="keyword" class="keyword">{{ keyword }}</span></div>
            <p class="result-abstract">{{ detailPaper.abstract || "暂无摘要。" }}</p>
            <a v-if="detailPaper.source_url" class="source-link" :href="detailPaper.source_url" target="_blank" rel="noreferrer">打开原文链接 ↗</a>
          </div>
        </section>
      </div>
    </teleport>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import { getErrorMessage, papersApi } from "../api"
import AppShell from "../components/AppShell.vue"
import PaperForm from "../components/PaperForm.vue"
import PaperTable from "../components/PaperTable.vue"

const route = useRoute()
const router = useRouter()
function readRouteFilters() {
  return {
    q: typeof route.query.q === "string" ? route.query.q : "",
    conference: typeof route.query.conference === "string" ? route.query.conference : "",
    year: route.query.year ? Number(route.query.year) : "",
    year_from: route.query.year_from ? Number(route.query.year_from) : "",
    year_to: route.query.year_to ? Number(route.query.year_to) : "",
    keyword: typeof route.query.keyword === "string" ? route.query.keyword : "",
  }
}
const filters = reactive(readRouteFilters())
const page = ref(1)
const pageSize = 15
const items = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref("")
const searched = ref(Boolean(filters.q || filters.conference || filters.year || filters.year_from || filters.year_to || filters.keyword))
const formVisible = ref(false)
const editingPaper = ref(null)
const detailPaper = ref(null)
const saveLoading = ref(false)
const lookupLoading = ref(false)
const saveLookupLoading = ref(false)
const lookupPaper = ref(null)
const lookupError = ref("")
const exportLoading = ref(false)
const exportError = ref("")
let requestSequence = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function queryParams() {
  const params = { page: page.value, page_size: pageSize }
  for (const key of ["q", "conference", "year", "year_from", "year_to", "keyword"]) {
    if (filters[key] !== "" && filters[key] !== null && filters[key] !== undefined) params[key] = filters[key]
  }
  return params
}

async function load() {
  const requestId = ++requestSequence
  loading.value = true
  error.value = ""
  try {
    const response = await papersApi.list(queryParams())
    if (requestId !== requestSequence) return
    items.value = response.data.items
    total.value = response.data.total
  } catch (cause) {
    if (requestId !== requestSequence) return
    error.value = getErrorMessage(cause, "论文接口暂时不可用")
  } finally {
    if (requestId === requestSequence) loading.value = false
  }
}

function syncRoute() {
  router.replace({ name: "papers", query: Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "" && value !== null && value !== undefined)) })
}
async function search() {
  page.value = 1
  searched.value = true
  lookupPaper.value = null
  lookupError.value = ""
  syncRoute()
  await load()
}
async function reset() {
  Object.assign(filters, { q: "", conference: "", year: "", year_from: "", year_to: "", keyword: "" })
  page.value = 1
  searched.value = false
  lookupPaper.value = null
  lookupError.value = ""
  syncRoute()
  await load()
}
function changePage(nextPage) {
  page.value = nextPage
  load()
}
function exportParams() {
  const params = {}
  for (const key of ["q", "conference", "year", "year_from", "year_to", "keyword"]) {
    if (filters[key] !== "" && filters[key] !== null && filters[key] !== undefined) params[key] = filters[key]
  }
  return params
}
async function downloadExport(format) {
  exportLoading.value = true
  exportError.value = ""
  try {
    const response = await papersApi.export(format, exportParams())
    const data = response.data instanceof Blob ? response.data : new Blob([response.data])
    const urlApi = window.URL || window.webkitURL
    if (!urlApi?.createObjectURL) throw new Error("当前浏览器不支持文件下载")
    const objectUrl = urlApi.createObjectURL(data)
    const link = document.createElement("a")
    link.href = objectUrl
    link.download = format === "csv" ? "cvinsight-papers.csv" : "cvinsight-papers.bib"
    document.body.appendChild(link)
    link.click()
    link.remove()
    urlApi.revokeObjectURL?.(objectUrl)
  } catch (cause) {
    exportError.value = getErrorMessage(cause, "论文导出失败")
  } finally {
    exportLoading.value = false
  }
}
function openCreate() {
  editingPaper.value = null
  formVisible.value = true
}
function openEdit(paper) {
  editingPaper.value = paper
  formVisible.value = true
}
function closeForm() {
  formVisible.value = false
  editingPaper.value = null
}
function openDetail(paper) {
  detailPaper.value = paper
}
async function savePaper(payload) {
  saveLoading.value = true
  error.value = ""
  try {
    if (editingPaper.value) await papersApi.update(editingPaper.value.id, payload)
    else await papersApi.create(payload)
    closeForm()
    await load()
  } catch (cause) {
    error.value = getErrorMessage(cause, "论文保存失败")
  } finally {
    saveLoading.value = false
  }
}
async function removePaper(paper) {
  if (!window.confirm("确定删除“" + paper.title + "”吗？")) return
  try {
    await papersApi.remove(paper.id)
    if (items.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (cause) {
    error.value = getErrorMessage(cause, "论文删除失败")
  }
}
async function lookupOnline() {
  lookupLoading.value = true
  lookupError.value = ""
  try {
    const response = await papersApi.lookup(filters.q)
    lookupPaper.value = response.data
  } catch (cause) {
    lookupError.value = getErrorMessage(cause, "在线检索失败，请检查后端检索源配置")
  } finally {
    lookupLoading.value = false
  }
}
async function saveLookup() {
  if (!lookupPaper.value) return
  saveLookupLoading.value = true
  lookupError.value = ""
  try {
    await papersApi.create(lookupPaper.value)
    clearLookup()
    await search()
  } catch (cause) {
    lookupError.value = getErrorMessage(cause, "在线结果入库失败")
  } finally {
    saveLookupLoading.value = false
  }
}
function clearLookup() {
  lookupPaper.value = null
  lookupError.value = ""
}
watch(() => [route.query.q, route.query.conference, route.query.year, route.query.year_from, route.query.year_to, route.query.keyword], () => {
  Object.assign(filters, readRouteFilters())
  page.value = 1
  searched.value = Boolean(filters.q || filters.conference || filters.year || filters.year_from || filters.year_to || filters.keyword)
  load()
})
onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; margin-bottom: 24px; }
.page-actions, .search-actions { display: flex; gap: 8px; align-items: center; }
.search-panel { display: grid; grid-template-columns: minmax(220px, 1.6fr) repeat(5, minmax(120px, 1fr)) auto; gap: 12px; align-items: end; padding: 16px; margin-bottom: 18px; }
.search-panel label { display: grid; gap: 5px; color: var(--text-soft); font-size: 12px; }
.search-field { min-width: 0; }
.year-field { max-width: 130px; }
.result-bar { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin: 15px 2px 10px; font-size: 12px; }
.export-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; }
.export-actions .button { min-height: 30px; padding: 5px 9px; font-size: 11px; }
.export-error { color: var(--coral); font-size: 11px; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 15px; padding: 16px; border-top: 1px solid var(--line); }
.lookup-prompt, .lookup-result { display: flex; align-items: center; justify-content: space-between; gap: 22px; padding: 20px; margin-top: 18px; }
.lookup-prompt h2 { margin: 4px 0; font: 600 20px var(--serif); }
.lookup-prompt p { margin: 6px 0 0; color: var(--text-soft); }
.lookup-error { margin-top: 18px; }
.lookup-result { display: block; padding: 0; }
.lookup-result .panel-heading h2 { max-width: 700px; font-size: 20px; }
.result-meta { display: flex; flex-wrap: wrap; gap: 12px; color: var(--text-soft); font: 11px var(--mono); }
.result-meta .venue { color: var(--cyan); }
.result-authors { color: var(--text-soft); }
.keyword-list { display: flex; flex-wrap: wrap; gap: 6px; }
.keyword { padding: 4px 7px; border: 1px solid rgba(34, 211, 238, .25); border-radius: 3px; color: var(--cyan); font: 11px var(--mono); }
.result-abstract { color: var(--text-soft); white-space: pre-wrap; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.source-link { color: var(--cyan); }
.icon-button { border: 0; background: transparent; color: var(--text-soft); font-size: 24px; line-height: 1; }
.icon-button:hover { color: var(--cyan); }
.modal-backdrop { position: fixed; inset: 0; z-index: 20; display: grid; place-items: center; padding: 20px; background: rgba(0, 0, 0, .72); }
.modal { width: min(820px, 100%); max-height: calc(100vh - 40px); overflow: auto; }
.detail-modal { width: min(760px, 100%); }
.detail-body h3 { margin: 0 0 12px; font: 600 24px/1.35 var(--serif); }
.detail-body { padding: 24px; }
.retry { margin-left: 8px; min-height: 32px; }
@media (max-width: 1100px) { .search-panel { grid-template-columns: 1fr 1fr; } .search-field { grid-column: 1 / -1; } }
@media (max-width: 620px) { .page-head { display: block; } .page-actions { margin-top: 16px; } .search-panel { grid-template-columns: 1fr; } .search-field { grid-column: auto; } .result-bar, .lookup-prompt { display: block; } .export-actions { justify-content: flex-start; margin-top: 12px; } .lookup-prompt .button { margin-top: 14px; } }
</style>
