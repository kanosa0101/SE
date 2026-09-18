<template>
  <div v-if="summary" class="result-panel">
    <div class="result-counts"><span class="success">已入库 {{ summary.created }}</span><span class="skipped">已跳过 {{ summary.skipped }}</span><span class="error">错误 {{ summary.errors }}</span></div>
    <div class="result-list"><div v-for="item in summary.items" :key="item.row" class="result-row"><span class="mono">第 {{ item.row }} 行</span><strong>{{ item.title || "未命名记录" }}</strong><span :class="item.status">{{ item.message }}</span></div></div>
  </div>
</template>

<script setup>
defineProps({ summary: { type: Object, default: null } })
</script>

<style scoped>
.result-panel { margin-top: 18px; }
.result-counts { display: flex; gap: 16px; margin-bottom: 12px; font: 12px var(--mono); }
.success { color: var(--green); }
.skipped { color: var(--amber); }
.error { color: var(--coral); }
.result-list { display: grid; gap: 5px; }
.result-row { display: grid; grid-template-columns: 72px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--line); color: var(--text-soft); font-size: 12px; }
.result-row strong { overflow: hidden; color: var(--text); text-overflow: ellipsis; white-space: nowrap; }
.result-row .created { color: var(--green); }
.result-row .skipped { color: var(--amber); }
.result-row .error { color: var(--coral); }
@media (max-width: 620px) { .result-row { grid-template-columns: 1fr; gap: 4px; } }
</style>

