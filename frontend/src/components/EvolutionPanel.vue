<template>
  <article class="panel evolution-panel" aria-labelledby="evolution-title">
    <div class="panel-heading evolution-heading">
      <div>
        <div class="eyebrow">EVOLUTION / ANNUAL HOTWORDS</div>
        <h2 id="evolution-title">年度热词演变</h2>
        <p class="panel-caption">全量样本年度帧 · 每帧展示最多 10 个热点方向</p>
      </div>
      <div class="evolution-tools">
        <button class="button secondary" type="button" aria-label="上一年" :disabled="loading || !frames.length" @click="previousFrame">‹</button>
        <button v-if="!playing" class="button secondary" type="button" aria-label="播放" :disabled="loading || frames.length < 2" @click="startPlayback">播放</button>
        <button v-else class="button secondary" type="button" aria-label="暂停" @click="stopPlayback">暂停</button>
        <button class="button secondary" type="button" aria-label="下一年" :disabled="loading || !frames.length" @click="nextFrame">›</button>
        <label class="speed-select">速度 <select v-model.number="speed" aria-label="演变播放速度"><option :value="1">1x</option><option :value="1.5">1.5x</option><option :value="2">2x</option></select></label>
      </div>
    </div>

    <div v-if="loading" class="loading-box evolution-state">正在读取年度帧……</div>
    <div v-else-if="error" class="error-box evolution-state">{{ error }} <button class="button secondary retry" type="button" @click="load">重试</button></div>
    <div v-else-if="!frames.length" class="empty-box evolution-state">暂无年度热词数据</div>
    <div v-else class="evolution-content">
      <div class="timeline" aria-label="年度选择">
        <button v-for="(frame, index) in frames" :key="frame.year" class="timeline-step" :class="{ active: index === activeIndex }" type="button" :aria-label="`切换到 ${frame.year} 年`" :aria-pressed="index === activeIndex" @click="setFrame(index)">{{ frame.year }}</button>
      </div>
      <div class="evolution-year"><span class="eyebrow">FRAME / YEAR</span><strong>{{ activeFrame.year }}</strong><span class="mono dim">{{ currentTopics.length }} topics</span></div>
      <div class="evolution-list">
        <div v-for="(topic, index) in currentTopics" :key="topic.keyword" class="evolution-row">
          <span class="evolution-rank">{{ String(index + 1).padStart(2, "0") }}</span>
          <span class="evolution-keyword">{{ topic.keyword }}</span>
          <span class="evolution-bar"><span :style="{ width: `${heatWidth(topic.heat)}%` }" /></span>
          <span class="evolution-heat">{{ formatHeat(topic.heat) }}</span>
          <span class="evolution-papers">{{ topic.papers }} 篇</span>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"

import { getErrorMessage, statsApi } from "../api"
import { formatHeat } from "../utils/filters"

const props = defineProps({ limit: { type: Number, default: 10 } })
const years = ref([])
const frames = ref([])
const activeIndex = ref(0)
const speed = ref(1)
const playing = ref(false)
const loading = ref(true)
const error = ref("")
const requestId = ref(0)
let timer

const activeFrame = computed(() => frames.value[activeIndex.value] || { year: "—", topics: [] })
const currentTopics = computed(() => (activeFrame.value.topics || []).slice(0, 10))
const maxHeat = computed(() => Math.max(1, ...currentTopics.value.map((topic) => Number(topic.heat) || 0)))

function heatWidth(value) {
  return Math.max(4, Math.round(((Number(value) || 0) / maxHeat.value) * 100))
}

function stopPlayback() {
  if (timer && typeof window !== "undefined") window.clearInterval(timer)
  timer = undefined
  playing.value = false
}

function advanceFrame() {
  if (activeIndex.value >= frames.value.length - 1) {
    stopPlayback()
    return
  }
  activeIndex.value += 1
}

function startPlayback() {
  stopPlayback()
  if (frames.value.length < 2) return
  if (activeIndex.value >= frames.value.length - 1) activeIndex.value = 0
  playing.value = true
  timer = window.setInterval(advanceFrame, 1200 / Number(speed.value))
}

function previousFrame() {
  stopPlayback()
  activeIndex.value = Math.max(0, activeIndex.value - 1)
}

function nextFrame() {
  stopPlayback()
  activeIndex.value = Math.min(frames.value.length - 1, activeIndex.value + 1)
}

function setFrame(index) {
  stopPlayback()
  activeIndex.value = Math.max(0, Math.min(frames.value.length - 1, index))
}

async function load() {
  const currentRequest = ++requestId.value
  stopPlayback()
  loading.value = true
  error.value = ""
  try {
    const response = await statsApi.evolution(props.limit)
    if (currentRequest !== requestId.value) return
    years.value = response.data.years || []
    frames.value = response.data.frames || []
    activeIndex.value = 0
  } catch (cause) {
    if (currentRequest !== requestId.value) return
    years.value = []
    frames.value = []
    error.value = getErrorMessage(cause, "年度演变接口暂时不可用")
  } finally {
    if (currentRequest === requestId.value) loading.value = false
  }
}

watch(speed, () => { if (playing.value) startPlayback() })
watch(() => props.limit, load)
onMounted(load)
onBeforeUnmount(() => { requestId.value += 1; stopPlayback() })
</script>

<style scoped>
.evolution-panel { margin-bottom: 18px; }
.evolution-heading { align-items: start; }
.panel-caption { margin: 7px 0 0; color: var(--text-dim); font-size: 11px; }
.evolution-tools { display: flex; align-items: center; gap: 7px; }
.evolution-tools .button { min-height: 32px; padding: 0 10px; }
.speed-select { color: var(--text-soft); font-size: 12px; white-space: nowrap; }
.speed-select select { margin-left: 4px; border: 1px solid var(--line); background: var(--surface-container-low); color: var(--text); }
.evolution-state { margin: 4px 0 8px; }
.timeline { display: flex; gap: 5px; overflow-x: auto; padding: 2px 0 14px; border-bottom: 1px solid var(--line); }
.timeline-step { padding: 5px 8px; border: 1px solid var(--outline-variant); border-radius: var(--radius-sm); background: var(--surface-container-low); color: var(--text-dim); font: 10px var(--mono); }
.timeline-step:hover, .timeline-step.active { border-color: var(--cyan); color: var(--cyan); }
.evolution-year { display: flex; align-items: baseline; gap: 10px; padding: 17px 0 12px; }
.evolution-year strong { color: var(--cyan); font: 600 26px var(--mono); }
.evolution-list { display: grid; gap: 7px; }
.evolution-row { display: grid; grid-template-columns: 32px minmax(130px, .7fr) minmax(100px, 1fr) 54px 58px; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid transparent; border-radius: var(--radius-sm); background: rgba(7, 12, 22, .42); }
.evolution-rank, .evolution-heat, .evolution-papers { color: var(--text-dim); font: 10px var(--mono); }
.evolution-rank { color: var(--cyan); }
.evolution-keyword { overflow: hidden; color: var(--text); text-overflow: ellipsis; white-space: nowrap; }
.evolution-bar { height: 5px; overflow: hidden; border-radius: 99px; background: var(--surface-container-high); }
.evolution-bar span { display: block; height: 100%; border-radius: inherit; background: var(--green); box-shadow: 0 0 10px rgba(78, 222, 163, .3); transition: width .2s ease; }
.evolution-heat { color: var(--amber); text-align: right; }
.evolution-papers { text-align: right; }
@media (max-width: 760px) { .evolution-heading { display: block; } .evolution-tools { justify-content: flex-start; flex-wrap: wrap; margin-top: 14px; } .evolution-row { grid-template-columns: 27px minmax(100px, 1fr) 80px 48px; } .evolution-papers { display: none; } }
</style>
