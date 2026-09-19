# CVInsight：顶会论文热词统计平台

| 项目 | 内容 |
| --- | --- |
| 学号 | 102400330 |
| 作业链接 | [软件工程实践第二次作业——与AI结对编程（顶会热词统计）](https://bbs.csdn.net/topics/620526318) |
| 代码规范 | [codestyle.md](./codestyle.md) |

CVInsight 是软件工程实践第二次作业的可运行实现。系统面向 CVPR、ICCV、ECCV 论文元数据，提供论文采集、论文库维护、Top 10 热词统计、关键词关系图谱和多年份趋势观察。

本仓库采用 Vue 3 + FastAPI + SQLite。Stitch 只用于前期原型和视觉方向探索；仓库中的页面、组件和接口代码按照本项目的数据模型重新实现，没有把 Stitch 生成的独立 HTML 作为应用代码直接接入。项目源码、测试和本 README 是可复核的工程内容；AI 协作记录、博客草稿和 PSP 属于提交者的个人课程材料，保留在本地但不纳入本项目 Git。

## 当前实现范围

- 单篇标题检索：展示摘要、作者、会议、年份、关键词和原文链接，确认后写入 SQLite。
- CSV 批量导入：逐行校验、重复跳过、错误回传，并保留导入结果。
- 论文库：标题、作者、论文编号和关键词的模糊查询；会议、年份、关键词筛选；详情、编辑和删除。
- 统计总览：论文数、会议数、年份范围、Top 10 关键词、关键词共现图。
- 趋势观察：按 CVPR、ICCV、ECCV 和年份返回论文数量，可在前端播放多年份折线动画。
- 数据接入：SQLAlchemy ORM + SQLite；关键词使用独立表和多对多关系保存。
- 生产入口：Vite 构建后由 FastAPI 提供前端静态资源，也可使用 Docker Compose 部署。
- 可重复演示数据：data/demo_papers.csv 包含 15 条跨年份演示记录，明确标记为 fixture。
- CVF 抓取样本：data/cvf_crawled_1500.csv（1502 条，CVPR 2022-2025、ICCV 2023/2025）与 data/cvf_pre2022.csv（10908 条，CVPR 2016-2021、ICCV 2017/2019/2021、ECCV 2018，另附 cvf_pre2022.manifest.json 抓取清单）均为真实抓取，抓取脚本为 backend/scripts/crawl_cvf.py。
- 扩展功能：关键词“了解更多”主题检查器、年度热词演变播放、数据质量审计以及 CSV/BibTeX 导出。

## 目录结构

~~~text
102400330/
├─ backend/
│  ├─ app/
│  │  ├─ api/              # papers、stats 路由
│  │  ├─ services/         # 论文、关键词、统计、在线检索逻辑
│  │  ├─ config.py         # 环境变量配置
│  │  ├─ db.py             # Engine、Session、建表
│  │  ├─ models.py         # Paper、Keyword、PaperKeyword
│  │  ├─ schemas.py        # Pydantic 请求/响应模型
│  │  └─ main.py           # FastAPI、CORS、静态托管
│  ├─ scripts/seed_demo.py # 导入演示数据
│  ├─ tests/               # 后端测试
│  └─ requirements.txt
├─ frontend/
│  ├─ src/components/      # AppShell、论文表格、表单、图表
│  ├─ src/views/           # 总览、论文库、导入、趋势、说明
│  └─ src/utils/           # 可测试的格式化与筛选函数
├─ data/demo_papers.csv
├─ data/cvf_crawled_1500.csv
├─ data/cvf_pre2022.csv
├─ data/cvf_pre2022.manifest.json
├─ docs/
├─ Dockerfile
└─ docker-compose.yml
~~~

## 本地开发

后端建议在 backend 目录运行：

~~~powershell
Set-Location backend
python -m venv .venv
& .venv/Scripts/Activate.ps1
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8000
~~~

另开终端启动前端开发服务器：

~~~powershell
Set-Location frontend
npm ci
npm run dev
~~~

开发服务器默认访问 http://localhost:5173。默认后端数据库为 backend/cvinsight.db；该文件被 .gitignore 忽略。在线检索源是可选配置，复制 backend/.env.example 为 backend/.env 后填写 CVINSIGHT_LOOKUP_URL 即可启用。

## 生产构建

先构建前端，再从 backend 目录启动 FastAPI：

~~~powershell
Set-Location frontend
npm ci
npm run build
Set-Location ../backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
~~~

构建完成后访问 http://localhost:8000，FastAPI 会返回 frontend/dist/index.html；前端资源使用 /assets 路径。跨域来源由 CVINSIGHT_CORS_ORIGINS 控制。

容器方式：

~~~powershell
docker compose config --quiet
docker compose up -d --build
Invoke-WebRequest http://127.0.0.1:8000/api/health
~~~

云主机或 CodeArts 的具体步骤见 deploy/README.md。当前仓库不包含任何真实云账号、服务器公网地址或部署密钥，因此不会把云端部署写成已完成事实。

## 测试与验证

后端：

~~~powershell
Set-Location backend
python -m pytest -q
~~~

前端：

~~~powershell
Set-Location frontend
npm run test -- --run
npm run build
~~~

当前本地验证记录：

- 后端：85 passed；包含 API、数据库迁移、统计扩展、CVF 抓取器（含老年份链接解析与分日页发现）、在线检索会议映射和趋势排序测试。
- 前端：29 passed；覆盖真实 API 状态、主题检查器、年度演变、质量审计和导出交互。
- Vite：生产构建成功；ECharts 按需引入并单独分包（echarts chunk 约 525 kB），构建无体积警告。
- CVF 数据：data/cvf_crawled_1500.csv（1502 条，CVPR 2022-2025、ICCV 2023/2025）+ data/cvf_pre2022.csv（10908 条，CVPR 2016-2021、ICCV 2017/2019/2021、ECCV 2018）；导入后数据库共 12419 条（含 15 条 fixture）。
- 抓取边界：ECCV 2020/2022/2024 地址返回 404（manifest 保留失败状态），没有用合成数据替代。
- 在线检索：backend/.env 已配置 OpenAlex 公共接口（https://api.openalex.org/works），/api/papers/lookup 已实测返回 CVPR 论文并正确映射会议缩写。
- Docker Compose：docker compose config --quiet 解析成功。
- 未验证项：华为云 CodeArts 构建、云主机公网访问，需要在拥有对应账号后执行。

## API 入口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /api/health | 服务健康检查 |
| GET | /api/papers | 论文分页、模糊查询和筛选 |
| GET | /api/papers/{id} | 读取论文详情 |
| POST | /api/papers | 新建论文 |
| PUT | /api/papers/{id} | 修改论文 |
| DELETE | /api/papers/{id} | 删除论文 |
| GET | /api/papers/lookup | 按标题调用配置好的在线来源 |
| POST | /api/papers/import | 上传 CSV 并批量入库 |
| GET | /api/stats/overview | 总量与年份范围 |
| GET | /api/stats/topics | Top 10 热词及热度 |
| GET | /api/stats/graph | 关键词节点和共现边 |
| GET | /api/stats/trends | 多年份会议趋势 |
| GET | /api/stats/topics/{keyword}/inspector | 主题详情、相关词和代表论文 |
| GET | /api/stats/evolution | 按年度返回热词演变帧 |
| GET | /api/stats/quality | 数据覆盖率、来源和质量审计 |
| GET | /api/papers/export | 按当前筛选条件导出 CSV/BibTeX |

论文列表接口参数包括 q、conference、year、keyword、page 和 page_size。统计接口支持 conference、year_from、year_to。具体字段以 backend/app/schemas.py 为准。

## 真实数据抓取与导入

backend/scripts/crawl_cvf.py 使用 BeautifulSoup 解析 CVF 会议页，保存 HTML 缓存、manifest 和 CSV，并支持限速、重试、断点续跑与按 source_url 去重；同时兼容 CVF 新旧页面结构（2021 起的 day=all 汇总页与 2016-2020 的分日动态页）。本次样本覆盖 CVPR 2016-2025、ICCV 2017/2019/2021/2023/2025 和 ECCV 2018；ECCV 2020/2022/2024 请求返回 404，manifest 保留失败状态，未补造论文。

仓库中的 data/cvf_crawled_1500.csv（1502 条）与 data/cvf_pre2022.csv（10908 条）是抓取并校验后的真实记录，合计 12410 条唯一 source_url。它们是可复核的真实抓取样本，不等同于所有顶会论文全集；使用前应确认来源页面的许可和课程提交要求。导入时可使用论文导入接口或页面的 CSV 批量导入；data/demo_papers.csv 仍用于无网络的最小演示。

## 统计口径

关键词提取采用可重复的规则：

1. 用户或导入文件提供关键词时，先进行小写化、空白清理、别名归一化和去重。
2. 没有提供关键词时，对标题和摘要执行 TF-IDF，去除常见停用词，取有限数量的高分词。
3. 关键词关系边表示两篇论文关键词集合在同一篇论文中的共现次数。
4. 热度定义为 keyword 覆盖论文数 / 当前筛选范围论文总数 × 1000。
5. 趋势图展示当前数据库记录数，不把演示夹具的数量解释为领域真实发表量。

因此，系统的结果依赖当前数据库内容；使用完整官方数据集前，不应把演示结果写成顶会总体研究趋势结论。

## 数据库模型

- Paper：标题、规范化标题、论文编号、摘要、作者、会议、年份、来源和原文链接。
- Keyword：归一化关键词名。
- PaperKeyword：论文与关键词关系、关键词分数和提取方法。
- 约束：同一会议、年份和规范化标题不可重复；论文删除时关联关键词关系一并删除。

## 版本与分支

- dev：日常实现和验证分支。
- main：交付分支，在 dev 完成验证后合并。
- release：合并 main 后创建 v1.0.0 标签。
- 提交信息使用 feat、fix、test、docs、chore 等前缀，并要求一个提交只对应一个可解释的工作单元。

## 课程提交材料（不纳入本项目 Git）

以下材料属于个人课程提交附件，保留在本地即可，不作为项目源码提交。

1. Stitch 原型公开链接和原型截图。
2. 真实的华为云 CodeArts/云主机地址、构建记录和部署截图。
3. 10 张以上页面或 GIF 截图。
4. 个人 PSP 实际耗时，不要直接把 AI 运行时间当成个人工时。
5. 聊天记录原文、三个代表性 AI 协作案例、采纳/拒绝理由和 AI 代码披露。
6. 使用真实数据集时的数据下载时间、字段映射、清洗规则和数据许可证。

这些内容需要提交者根据自己的账号、截图和真实操作补写。真实抓取数据的下载时间、字段映射、清洗规则与来源许可也应在博客中补充。
