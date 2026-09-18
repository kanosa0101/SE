<template>
  <article class="metric-card" :class="`tone-${tone}`">
    <div class="metric-label">{{ label }}</div>
    <div class="metric-value">{{ value }}</div>
    <div v-if="caption" class="metric-caption">{{ caption }}</div>
  </article>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  caption: { type: String, default: "" },
  tone: { type: String, default: "cyan" },
})
</script>

<style scoped>
.metric-card { min-height: 130px; padding: 18px; border: 1px solid var(--line); border-top: 2px solid var(--cyan); border-radius: var(--radius-md); background: linear-gradient(135deg, rgba(37, 42, 53, .85), rgba(22, 28, 38, .78)); }
.tone-amber { border-top-color: var(--amber); }
.tone-green { border-top-color: var(--green); }
.tone-coral { border-top-color: var(--coral); }
.metric-label, .metric-caption { color: var(--text-soft); font: 10px var(--mono); letter-spacing: .08em; text-transform: uppercase; }
.metric-value { margin: 14px 0 10px; color: var(--text); font: 600 clamp(24px, 3vw, 34px)/1 var(--mono); font-variant-numeric: tabular-nums; }
.metric-caption { color: var(--text-dim); font-size: 9px; }
</style>
