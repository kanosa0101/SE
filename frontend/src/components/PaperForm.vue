<template>
  <form class="paper-form" @submit.prevent="submit">
    <div class="form-grid">
      <label class="full">标题 <input v-model="form.title" class="field" required maxlength="500" /></label>
      <label>会议 <select v-model="form.conference" class="select" required><option value="CVPR">CVPR</option><option value="ICCV">ICCV</option><option value="ECCV">ECCV</option></select></label>
      <label>年份 <input v-model.number="form.year" class="field" type="number" min="1990" max="2100" required /></label>
      <label>论文编号 <input v-model="form.paper_code" class="field" placeholder="可选" /></label>
      <label>作者 <input v-model="form.authors" class="field" placeholder="可选" /></label>
      <label class="full">关键词 <input v-model="keywordText" class="field" placeholder="用逗号分隔，例如 diffusion, VLM" /></label>
      <label class="full">摘要 <textarea v-model="form.abstract" class="field" rows="6" /></label>
      <label class="full">原文链接 <input v-model="form.source_url" class="field" type="url" placeholder="https://..." /></label>
    </div>
    <div class="form-actions"><button class="button secondary" type="button" @click="$emit('cancel')">取消</button><button class="button" type="submit" :disabled="loading">{{ loading ? "保存中…" : "保存论文" }}</button></div>
  </form>
</template>

<script setup>
import { reactive, ref, watch } from "vue"

const props = defineProps({ paper: { type: Object, default: null }, loading: Boolean })
const emit = defineEmits(["save", "cancel"])
const form = reactive({ title: "", conference: "CVPR", year: new Date().getFullYear(), paper_code: "", authors: "", abstract: "", source_url: "", source: "manual" })
const keywordText = ref("")

function syncForm(paper) {
  Object.assign(form, {
    title: paper?.title || "",
    conference: paper?.conference || "CVPR",
    year: paper?.year || new Date().getFullYear(),
    paper_code: paper?.paper_code || "",
    authors: paper?.authors || "",
    abstract: paper?.abstract || "",
    source_url: paper?.source_url || "",
    source: paper?.source || "manual",
  })
  keywordText.value = (paper?.keywords || []).join(", ")
}
watch(() => props.paper, syncForm, { immediate: true })
function submit() {
  emit("save", { ...form, keywords: keywordText.value.split(/[,，;；|]/).map((item) => item.trim()).filter(Boolean) })
}
</script>

<style scoped>
.paper-form { padding: 22px; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.form-grid label { display: grid; gap: 6px; color: var(--text-soft); font-size: 12px; }
.form-grid .full { grid-column: 1 / -1; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
@media (max-width: 620px) { .form-grid { grid-template-columns: 1fr; } .form-grid .full { grid-column: auto; } }
</style>

