# CVInsight 视觉复刻与扩展功能设计

日期：2026-09-18  
基线：v1.0.0 / main / 90817c1  
目标分支：dev

## 1. 目标与边界

本次迭代同时解决五件事：

1. 以 Stitch 原型的 HTML、DESIGN.md 和页面截图为视觉基准，使用 Vue 组件重新实现，目标是页面结构和视觉效果近似 1:1。
2. 增加“了解更多”主题监察抽屉。
3. 增加年度热词演变动画。
4. 增加论文导出和数据质量审计等基础功能之外的能力。
5. 以 CVF Open Access 公开会议页面为主抓取 2022–2025 年 CVPR、ICCV、ECCV 论文，目标不少于当前 15 条演示记录的 100 倍，即约 1500 条；实际数量以公开目录可获取结果为准。

实现约束：

- 不直接接入 Stitch 最终 HTML，不把其 Tailwind 页面、内联脚本或静态演示数字复制到 Vue 页面。
- 只复用已确认的视觉语言：色彩、字体层级、间距、布局拓扑、页面文案结构和交互意图。
- 任何统计数字必须由 SQLite 当前数据计算；爬取不足时报告实际数量，不用合成重复论文补足。
- 真实数据源、抓取时间、字段映射、请求限速和解析失败数写入数据说明。
- 当前 v1.0.0 保留为基础功能发布；本迭代完成后使用新的增量版本发布。

## 2. Stitch 页面对照矩阵

| 原型页面 | Vue 页面 | 对照重点 | 业务绑定 |
| --- | --- | --- | --- |
| 主研究平台 | AppShell + OverviewView | 64px 顶栏、256px 导航、顶部搜索、会议胶囊、Telemetry 状态、12 列 Bento | overview/topics/graph API |
| _1 导入 | ImportView | 双栏工作区、来源状态、CSV 解析区、导入反馈和底部说明 | lookup/import API |
| _2 论文库 | PapersView | 论文卡片/表格、筛选条、会议标签、详情区域、右侧动作 | papers API |
| _3 趋势 | TrendsView | 会议切换、年份轨道、趋势图、播放控制、统计口径卡 | trends/evolution API |
| _4 总览 | OverviewView | 指标带、Top 10 排行、关系图、主题联动 | overview/topics/graph API |
| _5 方法论 | AboutView | 五级数据管线、统计公式、边界声明、系统状态 | quality API + 静态方法论 |

## 3. 视觉系统

tokens.css 将从当前简化变量扩展为与 DESIGN.md 对齐的命名：

- canvas：#070c16、#0b1220、#0e131e。
- surface：#111b2e、#161c26、#1b202a、#252a35。
- text：#f1f5f9、#dee2f1、#94a3b8、#64748b。
- semantic：cyan #06b6d4/#22d3ee、amber #f59e0b/#fbbf24、emerald #10b981/#34d399、coral #f43f5e。
- 字体：Noto Serif 用于标题和论文名，Inter 用于正文，JetBrains Mono 用于标签、数值、坐标和状态。
- 顶栏高度 64px，侧栏宽度 256px，桌面外边距 24px，常规间距 4/8/12/20/24/32px。
- 容器圆角以 2/4/6/8px 为主，不使用消费级大圆角。
- 面板只使用色阶和发丝边框表现层次，补充坐标标记、状态点和底部元数据条。
- 会议标签使用 CVPR-cyan、ICCV-amber、ECCV-emerald 三套状态色。

AppShell 负责全局结构；MetricCard、TelemetryBar、ConferenceChips、TopicRankList、TopicInspectorDrawer、PaperCard、MethodologyModule 和 DataQualityCard 负责复用结构。页面不再各自复制导航和卡片样式。

## 4. 数据抓取与入库

### 4.1 目标会议

优先尝试以下公开目录组合：

- CVPR：2022、2023、2024、2025。
- ICCV：2023、2025。
- ECCV：2022、2024。

爬虫也会对其余组合执行目录探测；HTTP 404 记录为该会议年份不存在或未开放，不视为程序异常。

### 4.2 流水线

1. 会议目录发现：读取 CVF Open Access 目录，提取论文详情页链接。
2. 原始缓存：按会议/年份/论文 URL 哈希保存 HTML 和 manifest，支持断点重跑。
3. 详情解析：解析标题、作者、摘要、会议、年份、论文 HTML/PDF 链接。
4. 关键词：优先使用页面显式关键词；没有关键词时调用已有的确定性 TF-IDF 提取。
5. 去重：以会议、年份和规范化标题作为业务唯一键；URL 哈希作为辅助键。
6. 输出：写入 UTF-8 CSV，同时输出成功数、重复数、解析失败数和缺失字段统计。
7. 入库：复用现有 import_csv 服务，单行失败不影响其他行。
8. 验证：先用每个会议年份 2 条样本做 parser test，再执行完整任务。

爬虫命令接口：

~~~text
python scripts/crawl_cvf.py --years 2022 2023 2024 2025 --venues CVPR ICCV ECCV --out ../data/cvf_2022_2025.csv --cache ../data/raw/cvf --delay 0.25 --workers 4
python scripts/crawl_cvf.py --resume --limit 20
~~~

默认限速、超时、重试和并发数必须可配置；默认值优先保护公开站点，不做高并发请求。DBLP 仅作为可选补充源，不覆盖 CVF 已解析字段。

### 4.3 可追溯字段

每条记录保留 source=cvf、source_url、conference、year、crawled_at、parser_version。当前 Paper 模型需要增加 crawled_at、parser_version 和 citation_key；旧的手工/fixture 数据使用空值或已有 source 标记。

## 5. 后端 API 设计

新增接口：

- GET /api/stats/topics/{keyword}/inspector
  - 返回 keyword、paper_count、heat、conference_breakdown、year_series、related_keywords、representative_papers。
  - 代表论文只返回必要元数据，完整摘要仍可从论文详情接口获取。
- GET /api/stats/evolution
  - 参数 conference、year_from、year_to、limit。
  - 返回 years 和每一年按 heat 降序排列的 topics。
- GET /api/stats/quality
  - 返回 total、missing_abstract、missing_source_url、keyword_coverage、source_breakdown、conference_year_matrix。
- GET /api/papers/export
  - 复用论文筛选参数，format=csv 或 format=bibtex。
  - 通过 StreamingResponse 返回下载文件，不在内存中复制无界数据。

现有接口保持兼容。统计服务抽出可测试的聚合函数，避免在路由中拼接业务逻辑。

## 6. 前端交互设计

### 6.1 了解更多

总览页的榜单行、图谱节点和趋势热词都触发同一个 TopicInspectorDrawer：

- 桌面端从右侧滑入 380px–440px 的 Tier 3 面板。
- 顶部显示主题名、热度、覆盖论文数和关闭按钮。
- 中部显示会议颜色分布、年度迷你折线和关联关键词。
- 底部列出最多 5 篇代表论文，点击进入论文详情。
- API 不可用时保留上次选择并展示错误；无论文时展示边界说明。
- 主题跳转到论文库时保留 keyword query，保证图谱点击仍可追溯。

### 6.2 年度热词演变

TrendsView 增加 EvolutionPanel：

- 年份轨道与原型中的 segmented control 对齐。
- 播放、暂停、上一年、下一年和速度 0.5x/1x/2x。
- 每个时间帧显示 Top 10 横向条形排行，条长为归一化热度，颜色按会议占比。
- 趋势折线保留，作为年度演变的连续视图。
- 动画只使用 API 返回的真实 years；数据不足时明确显示“该年份没有可用记录”。
- 前端单元测试覆盖帧切换、暂停和空数据。

### 6.3 扩展功能

- PapersView 增加 [ EXPORT CSV ] 和 [ EXPORT BIBTEX ] Ghost Action，沿用原型的 JetBrains Mono 括号文案。
- AboutView 增加真实数据质量审计卡：完整摘要比例、原文链接比例、关键词来源比例、按会议/年份的数据矩阵。
- ImportView 增加爬取说明和最近一次 manifest 摘要，但不在浏览器端执行高耗时爬取。
- 侧栏和页面底部增加当前数据源、抓取时间和 parser version。

## 7. 数据量和性能

- 目标基数：当前 15 条 fixture × 100 ≈ 1500 条真实记录。
- SQLite 需要为 Paper normalized_title、conference、year 建组合索引，为 Keyword.name 建索引。
- 论文列表默认 page_size=25；导出使用流式响应。
- 图谱默认只返回前 80 个节点和前 240 条边，点击主题后再请求详情。
- 年度演变默认每年 Top 10，避免把全部关键词发送到浏览器。
- 爬虫保存 manifest 后可从中断位置恢复，不重复请求已有 URL。

## 8. 错误和边界

- 目录不可访问：记录网络错误、跳过该会议年份，并返回非零退出码。
- 详情页缺摘要：保留论文，missing_abstract 加一，不能丢弃整条记录。
- 解析出非法年份/会议：记录 parser error，不入库。
- 重复论文：输出 skipped，不作为错误。
- 在线检索未配置：显示清晰提示，不能阻断本地数据浏览。
- 数据低于 1500：显示实际数量和原因，不生成虚拟论文。

## 9. 验证计划

后端：

- parser fixture：标题、作者、摘要、链接、会议和年份。
- crawl manifest：断点、重复 URL、限速参数。
- inspector/evolution/quality API：正常、空库和筛选条件。
- export：CSV 字段、BibTeX key、中文字符编码。

前端：

- AppShell 视觉 token 和导航状态。
- TopicInspectorDrawer 打开、关闭和错误状态。
- EvolutionPanel 帧切换和播放状态。
- PapersView 导出按钮和浏览器下载响应。
- 生产构建后 FastAPI 静态首页。

交付检查：

- 本地真实爬取结果数量和 manifest。
- 15×100 目标是否达到，未达到时有证据化说明。
- 五页与 Stitch 截图逐项比对。
- 后端、前端测试和生产构建均通过。
- dev 合并 main 后发布新的增量标签，并在博客中记录 v1.0.0 与本迭代的差异。

## 10. 明确不做

- 不把 Stitch HTML 文件作为 Vue 模板、iframe 或静态资源加载。
- 不用论文标题复制、随机年份或重复记录伪造 1500 条数据。
- 不把爬虫抓取量解释成完整的官方录用全集，除非目录覆盖和字段完整性已验证。
- 不在未配置云端凭据时声称完成华为云部署。

