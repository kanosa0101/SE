<template>
  <div class="telemetry-bar">
    <button class="drawer-toggle" type="button" aria-label="Toggle navigation" :aria-expanded="props.drawerOpen" :aria-controls="props.drawerId" @click="$emit('toggle-drawer')">☰</button>
    <div class="telemetry-count"><span class="signal" />{{ countLabel }} <span class="count-unit">RECORDS INDEXED</span></div>
    <button class="threshold-button" type="button" @click="$emit('threshold')"><span class="live-dot" />{{ timezone }} / LIVE</button>
    <span class="profile-marker" aria-label="Profile">CI</span>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  count: { type: [String, Number], default: null },
  timezone: { type: String, default: "UTC+08" },
  drawerOpen: { type: Boolean, default: false },
  drawerId: { type: String, default: "observatory-sidebar" },
})
defineEmits(["toggle-drawer", "threshold"])
const countLabel = computed(() => {
  const value = Number(props.count)
  return props.count === null || props.count === undefined || props.count === "" || !Number.isFinite(value) ? "—" : value.toLocaleString("en-US")
})
</script>

<style scoped>
.telemetry-bar { display: flex; align-items: center; justify-content: flex-end; gap: 14px; min-width: 280px; color: var(--text-soft); font: 10px var(--mono); letter-spacing: .06em; }
.drawer-toggle { display: none; border: 0; background: transparent; color: var(--cyan); font-size: 18px; }
.telemetry-count, .threshold-button { display: inline-flex; align-items: center; gap: 7px; }
.threshold-button { padding: 4px 0; border: 0; background: transparent; color: var(--text-dim); font: inherit; }
.threshold-button:hover { color: var(--cyan); }
.signal, .live-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--cyan); box-shadow: 0 0 10px rgba(76, 215, 246, .7); }
.live-dot { background: var(--green); box-shadow: 0 0 10px rgba(78, 222, 163, .7); }
.count-unit { color: var(--text-dim); font-size: 8px; }
.profile-marker { display: grid; width: 28px; height: 28px; place-items: center; border: 1px solid var(--outline-variant); border-radius: 50%; color: var(--amber); font-size: 9px; }
@media (max-width: 900px) { .drawer-toggle { display: block; } .count-unit { display: none; } .telemetry-bar { min-width: 0; gap: 8px; } }
</style>
