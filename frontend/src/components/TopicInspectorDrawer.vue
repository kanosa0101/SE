<template>
  <aside v-if="open" class="inspector-backdrop" @click.self="$emit('close')">
    <section ref="drawerElement" class="inspector-drawer" tabindex="-1" role="dialog" aria-modal="true" :aria-label="`${keyword} 主题详情`" @keydown="handleKeydown">
      <header class="inspector-head">
        <div>
          <div class="eyebrow">TOPIC / INSPECTOR</div>
          <h2>了解更多</h2>
          <p class="drawer-keyword">{{ keyword }}</p>
        </div>
        <button class="icon-button" type="button" aria-label="关闭主题详情" @click="$emit('close')">×</button>
      </header>

      <div v-if="loading" class="drawer-state">正在读取主题证据……</div>
      <div v-else-if="error" class="drawer-state error-state">
        <p>{{ error }}</p>
        <button class="button secondary" type="button" @click="runLoad">重新加载</button>
      </div>
      <div v-else-if="!details" class="drawer-state">暂无该主题的可用证据。</div>
      <div v-else class="drawer-content">
        <div class="topic-summary">
          <div><span class="summary-label">论文覆盖</span><strong>{{ details.papers }}</strong><small>篇</small></div>
          <div><span class="summary-label">热度</span><strong>{{ formatHeat(details.heat) }}</strong><small>覆盖率</small></div>
        </div>

        <section class="drawer-section">
          <div class="section-heading"><span>会议分布</span><span class="mono dim">{{ details.conference_breakdown.length }} venues</span></div>
          <div class="bar-list">
            <div v-for="item in details.conference_breakdown" :key="item.conference" class="bar-row">
              <span>{{ item.conference }}</span>
              <span class="bar-track"><span class="bar-fill cyan-fill" :style="{ width: `${barWidth(item.papers, maxConference)}%` }" /></span>
              <strong>{{ item.papers }}</strong>
            </div>
            <p v-if="!details.conference_breakdown.length" class="muted">暂无会议分布。</p>
          </div>
        </section>

        <section class="drawer-section">
          <div class="section-heading"><span>年度轨迹</span><span class="mono dim">论文数</span></div>
          <div class="year-bars">
            <div v-for="item in yearSeries" :key="item.year" class="year-bar" :title="`${item.year}: ${item.papers} 篇`">
              <span class="year-track"><span class="year-fill" :style="{ height: `${barWidth(item.papers, maxYear)}%` }" /></span>
              <small>{{ item.year }}</small>
            </div>
            <p v-if="!yearSeries.length" class="muted">暂无年度轨迹。</p>
          </div>
        </section>

        <section class="drawer-section">
          <div class="section-heading"><span>相关关键词</span><span class="mono dim">共现证据</span></div>
          <div class="related-list">
            <button v-for="item in details.related_keywords.slice(0, 8)" :key="item.keyword" class="related-chip" type="button" @click="$emit('select-related', item.keyword)">
              <span>{{ item.keyword }}</span><small>{{ item.papers }} 篇</small>
            </button>
            <p v-if="!details.related_keywords.length" class="muted">暂无相关关键词。</p>
          </div>
        </section>

        <section class="drawer-section papers-section">
          <div class="section-heading"><span>代表论文</span><span class="mono dim">{{ details.representative_papers.length }} items</span></div>
          <article v-for="paper in details.representative_papers.slice(0, 6)" :key="paper.paper_id" class="representative-paper">
            <div class="paper-meta"><span class="source-badge">{{ paper.source }}</span><span class="mono dim">{{ paper.conference }} · {{ paper.year }}</span></div>
            <h3>{{ paper.title }}</h3>
            <p>{{ paper.authors || '作者信息未提供' }}</p>
            <a v-if="paper.source_url" :href="paper.source_url" target="_blank" rel="noreferrer">查看来源 ↗</a>
          </article>
          <p v-if="!details.representative_papers.length" class="muted">暂无代表论文。</p>
          <button class="button primary full-button" type="button" @click="$emit('view-papers', keyword, scope)">查看该主题全部论文</button>
        </section>
      </div>
    </section>
  </aside>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue"

import { getErrorMessage, statsApi } from "../api"
import { formatHeat } from "../utils/filters"

const props = defineProps({
  keyword: { type: String, default: "" },
  scope: { type: String, default: "keyword" },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(["close", "select-related", "view-papers"])

const details = ref(null)
const loading = ref(false)
const error = ref("")
const loadRequestId = ref(0)
const drawerElement = ref(null)
const restoreFocusElement = ref(null)
const maxConference = computed(() => Math.max(1, ...(details.value?.conference_breakdown || []).map((item) => Number(item.papers) || 0)))
const yearSeries = computed(() => {
  const supplied = details.value?.year_series
  if (Array.isArray(supplied) && supplied.length) return supplied
  const counts = new Map()
  for (const paper of details.value?.representative_papers || []) {
    const year = Number(paper.year)
    if (!Number.isFinite(year)) continue
    counts.set(year, (counts.get(year) || 0) + 1)
  }
  return [...counts.entries()]
    .sort(([left], [right]) => left - right)
    .map(([year, papers]) => ({ year, papers }))
})
const maxYear = computed(() => Math.max(1, ...yearSeries.value.map((item) => Number(item.papers) || 0)))

function barWidth(value, maximum) {
  const numeric = Number(value) || 0
  return Math.max(4, Math.round((numeric / maximum) * 100))
}

async function load() {
  if (!props.keyword) return
  const requestId = ++loadRequestId.value
  loading.value = true
  error.value = ""
  try {
    const response = props.scope === "area"
      ? await statsApi.inspector(props.keyword, "area")
      : await statsApi.inspector(props.keyword)
    if (requestId !== loadRequestId.value) return
    details.value = response.data
  } catch (cause) {
    if (requestId !== loadRequestId.value) return
    details.value = null
    error.value = getErrorMessage(cause, "主题详情暂时不可用")
  } finally {
    if (requestId === loadRequestId.value) loading.value = false
  }
}

function handleKeydown(event) {
  if (event.key === "Escape") {
    emit("close")
    return
  }
  if (event.key !== "Tab") return
  const drawer = drawerElement.value
  if (!drawer) return
  const focusable = [...drawer.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
  if (!focusable.length) {
    event.preventDefault()
    drawer.focus()
    return
  }
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!drawer.contains(document.activeElement)) {
    event.preventDefault()
    first.focus()
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

async function focusDrawer() {
  if (typeof document === "undefined") return
  if (drawerElement.value) {
    if (document.activeElement !== drawerElement.value && !restoreFocusElement.value) {
      restoreFocusElement.value = document.activeElement
    }
    drawerElement.value.focus()
    return
  }
  if (!restoreFocusElement.value) restoreFocusElement.value = document.activeElement
  await nextTick()
  drawerElement.value?.focus()
}

function restoreFocus() {
  const target = restoreFocusElement.value
  restoreFocusElement.value = null
  if (target && typeof target.focus === "function") target.focus()
}

function runLoad() {
  load().catch((cause) => {
    if (!props.open) return
    details.value = null
    error.value = getErrorMessage(cause, "主题详情暂时不可用")
    loading.value = false
  })
}

watch(() => [props.open, props.keyword, props.scope], async ([open, keyword], previous) => {
  const wasOpen = Boolean(previous?.[0])
  if (!open || !keyword) {
    details.value = null
    error.value = ""
    loading.value = false
    loadRequestId.value += 1
    if (wasOpen && !open) restoreFocus()
    return
  }
  if (!wasOpen) await focusDrawer()
  if (!props.open || props.keyword !== keyword) return
  runLoad()
}, { immediate: true })

onMounted(() => {
  if (props.open && props.keyword) focusDrawer()
})
</script>

<style scoped>
.inspector-backdrop { position: fixed; z-index: 30; inset: 0; display: flex; justify-content: flex-end; background: rgba(3, 7, 14, .58); backdrop-filter: blur(4px); }
.inspector-drawer { display: flex; width: min(520px, 100vw); height: 100%; flex-direction: column; overflow: hidden; border-left: 1px solid var(--outline-variant); background: var(--surface-container-lowest); box-shadow: -24px 0 60px rgba(0, 0, 0, .35); }
.inspector-head { display: flex; align-items: start; justify-content: space-between; gap: 16px; padding: 24px 24px 18px; border-bottom: 1px solid var(--line); background: var(--surface-container-low); }
.inspector-head h2 { margin: 5px 0 0; font-family: var(--serif); font-size: 25px; font-weight: 500; }
.drawer-keyword { margin: 6px 0 0; color: var(--cyan); font: 12px var(--mono); }
.icon-button { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: transparent; color: var(--text-soft); font-size: 22px; line-height: 1; }
.icon-button:hover { border-color: var(--cyan); color: var(--cyan); }
.drawer-content { overflow: auto; padding: 18px 24px 30px; }
.drawer-state { display: grid; min-height: 180px; place-items: center; padding: 24px; color: var(--text-soft); text-align: center; }
.error-state { display: block; color: var(--coral); }
.error-state p { margin: 0 0 14px; }
.topic-summary { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
.topic-summary > div { display: grid; grid-template-columns: 1fr auto; gap: 4px 10px; padding: 14px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface-container-low); }
.summary-label { grid-column: 1 / -1; color: var(--text-dim); font: 9px var(--mono); letter-spacing: .1em; text-transform: uppercase; }
.topic-summary strong { color: var(--cyan); font: 600 24px var(--mono); }
.topic-summary small { align-self: end; color: var(--text-soft); font-size: 11px; }
.drawer-section { padding: 16px 0; border-top: 1px solid var(--line); }
.section-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; color: var(--text); font: 600 12px var(--mono); letter-spacing: .04em; }
.bar-list { display: grid; gap: 9px; }
.bar-row { display: grid; grid-template-columns: 62px 1fr 32px; align-items: center; gap: 8px; color: var(--text-soft); font: 11px var(--mono); }
.bar-row strong { color: var(--text); text-align: right; }
.bar-track { height: 6px; overflow: hidden; border-radius: 99px; background: var(--surface-container-high); }
.bar-fill { display: block; height: 100%; border-radius: inherit; }
.cyan-fill { background: var(--cyan); box-shadow: 0 0 10px rgba(76, 215, 246, .35); }
.year-bars { display: flex; align-items: end; gap: 8px; min-height: 104px; padding-top: 12px; }
.year-bar { display: flex; min-width: 28px; height: 88px; flex: 1; flex-direction: column; align-items: stretch; justify-content: flex-end; gap: 6px; text-align: center; }
.year-track { display: flex; width: 100%; min-height: 0; flex: 1; align-items: flex-end; }
.year-fill { display: block; width: 100%; min-height: 4px; border-radius: 3px 3px 0 0; background: var(--green); box-shadow: 0 0 12px rgba(78, 222, 163, .25); }
.year-bar small { color: var(--text-dim); font: 9px var(--mono); }
.related-list { display: flex; flex-wrap: wrap; gap: 7px; }
.related-chip { display: inline-flex; align-items: center; gap: 7px; padding: 7px 9px; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: var(--surface-container-low); color: var(--text-soft); font: 11px var(--mono); }
.related-chip:hover { border-color: var(--amber); color: var(--amber); }
.related-chip small { color: var(--text-dim); }
.representative-paper { padding: 12px 0; border-bottom: 1px solid var(--line); }
.paper-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.source-badge { padding: 3px 6px; border: 1px solid rgba(255, 185, 95, .35); border-radius: 3px; color: var(--amber); font: 9px var(--mono); text-transform: uppercase; }
.representative-paper h3 { margin: 8px 0 4px; color: var(--text); font: 500 14px/1.4 var(--serif); }
.representative-paper p { margin: 0 0 7px; overflow: hidden; color: var(--text-dim); font: 10px/1.5 var(--mono); text-overflow: ellipsis; white-space: nowrap; }
.representative-paper a { color: var(--cyan); font: 10px var(--mono); }
.representative-paper a:hover { color: var(--amber); }
.full-button { width: 100%; margin-top: 16px; }
.muted { color: var(--text-dim); font-size: 12px; }
@media (max-width: 600px) { .inspector-head { padding: 18px; } .drawer-content { padding: 16px 18px 24px; } }
</style>
