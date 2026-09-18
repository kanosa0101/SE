<template>
  <div class="conference-chips" aria-label="Conference filter">
    <button
      v-for="conference in conferences"
      :key="conference.value"
      class="conference-chip"
      :class="[`chip-${conference.tone}`, { active: modelValue === conference.value }]"
      type="button"
      :aria-pressed="modelValue === conference.value"
      @click="$emit('update:modelValue', conference.value)"
    >
      <span class="chip-signal" />{{ conference.label }}
    </button>
  </div>
</template>

<script setup>
defineProps({ modelValue: { type: String, default: "all" } })
defineEmits(["update:modelValue"])

const conferences = [
  { value: "all", label: "ALL", tone: "cyan" },
  { value: "cvpr", label: "CVPR", tone: "amber" },
  { value: "iccv", label: "ICCV", tone: "green" },
  { value: "eccv", label: "ECCV", tone: "coral" },
]
</script>

<style scoped>
.conference-chips { display: flex; align-items: center; gap: 4px; }
.conference-chip { display: inline-flex; align-items: center; gap: 5px; min-height: 24px; padding: 0 7px; border: 1px solid var(--line); border-radius: var(--radius-xs); background: transparent; color: var(--text-dim); font: 9px var(--mono); letter-spacing: .08em; }
.conference-chip:hover, .conference-chip.active { border-color: currentColor; background: var(--surface-container-highest); color: var(--text); }
.chip-signal { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.chip-cyan { color: var(--cyan); }
.chip-amber { color: var(--amber); }
.chip-green { color: var(--green); }
.chip-coral { color: var(--coral); }
</style>
