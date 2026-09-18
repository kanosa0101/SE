# CVInsight 编码规范

规范来源：Python PEP 8（https://peps.python.org/pep-0008/）、Black Code Style（https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html）、Vue Style Guide（https://vuejs.org/style-guide/）和 Conventional Commits 1.0.0（https://www.conventionalcommits.org/en/v1.0.0/）。本文件结合课程项目的 FastAPI、Vue 和 Git 约束做了项目化补充。

## 1. 基本原则

- 代码优先服务于作业需求，避免为单次使用场景增加无必要的抽象。
- 业务规则放在 services 中，HTTP 路由只负责参数、状态码和依赖注入。
- 输入输出模型集中放在 schemas.py，数据库结构集中放在 models.py。
- 统计结果必须带有明确口径，不使用无来源的固定数字填充页面。
- 外部数据要保留 source、source_url 和导入结果，便于追溯。
- 任何不能在本地验证的云端事实必须标注为待执行。

## 2. Python 与 FastAPI

- 使用 4 个空格缩进，函数和变量使用 snake_case，类使用 PascalCase。
- 公共服务函数写清楚输入和返回类型；跨模块调用优先依赖 schemas 中的模型。
- 路由按资源分组：论文接口在 api/papers.py，统计接口在 api/stats.py。
- 依赖数据库 Session 使用 Depends(get_db)，不要在路由中创建全局临时连接。
- 数据库提交由 services 负责；发生可预期冲突时转换为明确的业务异常。
- 面向用户的错误信息使用简短中文，内部异常保留 cause 链。
- 统计函数保持纯函数优先，输入和输出应可以用小样本测试。
- 运行测试使用 python -m pytest -q；新增接口至少覆盖成功路径和一个边界/错误路径。

## 3. SQLAlchemy

- 模型继承 Base，主键统一使用 Integer。
- 论文标题写入 normalized_title 后再参与去重。
- 多对多关系通过 PaperKeyword 保存，不在 Paper 表里拼接关键词字符串。
- 查询列表必须显式排序，分页参数必须限制最小值和最大值。
- 修改标题、会议或年份时重新检查重复约束。

## 4. Vue

- 页面使用 script setup，组件名使用 PascalCase，事件名使用短而明确的动词。
- AppShell 负责页面框架，页面视图负责数据加载和业务状态，展示组件尽量保持无副作用。
- 后端请求集中在 src/api.js，不在多个页面中重复拼接 API 地址。
- 加载、错误、空数据和成功状态需要分别呈现。
- 任何会改变数据的按钮都应有 disabled 状态或确认操作。
- 组件样式优先使用 tokens.css 中的颜色、字体和间距变量。
- 图表只消费 API 返回的数据，禁止把演示数值写死进图表组件。

## 5. Git

- 在 dev 分支开发，验证后合并到 main。
- 提交格式：type: short imperative description。
- 推荐类型：feat、fix、test、docs、chore、refactor。
- 一个提交只描述一个可复核的工作单元。
- 提交前运行 git diff --check、后端测试、前端测试和必要的生产构建。
- 不提交 .env、数据库文件、node_modules、dist 和个人截图原文件。
- 发布版本使用 vMAJOR.MINOR.PATCH，例如 v1.0.0。

## 6. 代码审查清单

- 是否能从接口或测试追溯到需求？
- 是否存在无来源的硬编码数据？
- 空数据库是否仍能正常渲染？
- 外部检索不可用时，本地论文管理是否仍可用？
- CSV 中的坏行是否只影响当前行？
- 删除论文后是否留下孤立关系？
- 文档是否区分已验证事实、假设和待执行操作？

