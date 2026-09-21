<template>
  <AppShell>
    <div class="page-head"><div class="eyebrow">METHODOLOGY / DISCLOSURE</div><h1 class="page-title">关于平台与统计口径</h1><p class="page-intro">研究趋势可视化的可信度来自数据来源、处理步骤和限制条件都被明确写出。</p></div>
    <section class="method-grid">
      <article class="panel method-card"><div class="eyebrow">01 / SOURCE</div><h2>数据来源</h2><p>平台接收 CVPR、ICCV、ECCV 论文元数据 CSV/TXT，也支持配置公开学术元数据检索源。每条论文记录保留 source 和 source_url。</p></article>
      <article class="panel method-card"><div class="eyebrow">02 / KEYWORDS</div><h2>关键词处理</h2><p>优先使用原始关键词；缺失时对标题与摘要执行英文停用词过滤、别名归一和 TF-IDF 提取，并在记录中标明提取方法。热门方向排名按作业口径聚合为研究领域（如 Object Detection、Diffusion & Generative Models、Vision-Language & Multimodal 等 15 类），以领域覆盖论文数排序，image、model 等泛化载体词不参与排名。</p></article>
      <article class="panel method-card"><div class="eyebrow">03 / METRIC</div><h2>热度公式</h2><div class="formula">heat = area_papers / total_papers × 1000‰</div><p>热门研究方向定义为：先把细粒度关键词按固定词元映射到研究领域，再按"覆盖论文数"降序排列并取前 10 个方向；未映射的泛化载体词（model、image、data 等）不参与排名。覆盖率单位是千分比（‰）：每 1000 篇论文中属于该方向的论文数量。同一篇论文可同时属于多个方向，因此各方向覆盖率之和可以超过 1000‰；单个方向的覆盖率本身不会超过 1000‰。统计单位是"包含相关关键词的论文数"，不是关键词在摘要中的原始出现次数。</p></article>
      <article class="panel method-card"><div class="eyebrow">04 / LIMITS</div><h2>使用边界</h2><p>热度仅用于研究趋势探索，不代表论文质量、学术影响力或会议录用评价。样本覆盖范围变化会影响比较结果。</p></article>
      <article class="panel method-card"><div class="eyebrow">05 / GRAPH</div><h2>关系图谱编码</h2><p>图谱取覆盖论文数前 50 的关键词。节点大小表示覆盖论文数；边表示两个关键词在同一篇论文中共同出现，连线粗细与深浅按共现论文数（1—447 篇）的平方根比例映射，悬停可查看数值。图谱默认只显示共现论文数 ≥ 75（约前 10%）的强关系主干，可用"显示全部关系"开关查看全部 1222 条边；过滤仅影响显示、不修改底层数据。</p></article>
    </section>
    <article class="panel pipeline"><div class="panel-heading"><div><div class="eyebrow">PIPELINE / TRACEABILITY</div><h2>数据处理流程</h2></div></div><div class="pipeline-steps"><div v-for="(step, index) in steps" :key="step" class="pipeline-step"><span>0{{ index + 1 }}</span><strong>{{ step }}</strong><i v-if="index < steps.length - 1">→</i></div></div></article>
    <DataQualityCard />
  </AppShell>
</template>

<script setup>
import AppShell from "../components/AppShell.vue"
import DataQualityCard from "../components/DataQualityCard.vue"

const steps = ["论文获取", "字段校验", "关键词归一", "热度统计", "关系图谱与趋势可视化"]
</script>

<style scoped>
.page-head { margin-bottom: 24px; }
.method-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; margin-bottom: 18px; }
.method-card { min-height: 210px; padding: 22px; }
.method-card h2 { margin: 12px 0; font: 600 22px var(--serif); }
.method-card p { margin: 0; color: var(--text-soft); line-height: 1.8; }
.formula { margin: 16px 0; padding: 14px; border: 1px solid rgba(34, 211, 238, 0.25); background: rgba(34, 211, 238, 0.06); color: var(--cyan); font: 15px var(--mono); }
.pipeline { overflow: hidden; }
.pipeline-steps { display: flex; align-items: center; gap: 14px; padding: 24px; overflow-x: auto; }
.pipeline-step { display: grid; min-width: 140px; gap: 8px; }
.pipeline-step span { color: var(--amber); font: 11px var(--mono); }
.pipeline-step strong { color: var(--text); }
.pipeline-step i { color: var(--cyan); font-style: normal; }
@media (max-width: 700px) { .method-grid { grid-template-columns: 1fr; } .pipeline-steps { align-items: flex-start; flex-direction: column; } .pipeline-step i { display: none; } }
</style>
