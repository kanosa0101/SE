<template>
  <div class="table-wrap">
    <table class="paper-table">
      <thead><tr><th>论文标题</th><th>会议 / 年份</th><th>关键词</th><th>来源</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="paper in items" :key="paper.id">
          <td><button class="title-button" type="button" @click="$emit('detail', paper)">{{ paper.title }}</button><div class="authors">{{ paper.authors || "作者信息未提供" }}</div></td>
          <td><span class="venue">{{ paper.conference }}</span><span class="year">{{ paper.year }}</span></td>
          <td><div class="keyword-list"><span v-for="keyword in paper.keywords.slice(0, 3)" :key="keyword" class="keyword">{{ keyword }}</span><span v-if="paper.keywords.length > 3" class="dim">+{{ paper.keywords.length - 3 }}</span></div></td>
          <td><span class="source">{{ paper.source || "unknown" }}</span><span v-if="paper.crawled_at" class="provenance">抓取 {{ formatTimestamp(paper.crawled_at) }}</span><span v-if="paper.parser_version" class="provenance">解析 {{ paper.parser_version }}</span></td>
          <td><div class="actions"><button type="button" title="编辑" @click="$emit('edit', paper)">编辑</button><button type="button" title="删除" class="danger" @click="$emit('delete', paper)">删除</button></div></td>
        </tr>
        <tr v-if="!items.length"><td colspan="5"><div class="empty-box compact">没有找到符合条件的论文。</div></td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
function formatTimestamp(value) {
  return String(value).replace("T", " ").replace(/Z$/, "")
}
defineEmits(["detail", "edit", "delete"])
</script>

<style scoped>
.table-wrap { overflow-x: auto; }
.paper-table { width: 100%; border-collapse: collapse; min-width: 760px; }
.paper-table th { padding: 12px 16px; border-bottom: 1px solid var(--line); color: var(--text-dim); font: 10px var(--mono); letter-spacing: .05em; text-align: left; }
.paper-table td { padding: 15px 16px; border-bottom: 1px solid rgba(148,163,184,.09); vertical-align: top; }
.title-button { max-width: 420px; padding: 0; border: 0; background: transparent; color: var(--text); font: 600 15px/1.4 var(--serif); text-align: left; }
.title-button:hover { color: var(--cyan); }
.authors { margin-top: 5px; max-width: 420px; overflow: hidden; color: var(--text-dim); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.venue, .year { display: block; font: 11px var(--mono); }
.venue { color: var(--cyan); }
.year { margin-top: 4px; color: var(--text-soft); }
.keyword-list { display: flex; flex-wrap: wrap; gap: 4px; max-width: 210px; }
.keyword { padding: 3px 6px; border: 1px solid rgba(34,211,238,.25); border-radius: 2px; color: var(--cyan); font: 10px var(--mono); }
.source { display: block; color: var(--text-soft); font: 11px var(--mono); }
.provenance { display: block; margin-top: 5px; color: var(--text-dim); font: 10px var(--mono); white-space: nowrap; }
.actions { display: flex; gap: 6px; }
.actions button { padding: 5px 8px; border: 1px solid var(--line); border-radius: 3px; background: var(--ink-900); color: var(--text-soft); font-size: 11px; }
.actions button:hover { border-color: var(--cyan); color: var(--cyan); }
.actions .danger:hover { border-color: var(--coral); color: var(--coral); }
</style>
