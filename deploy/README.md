# CVInsight 部署说明

本目录描述容器化部署路径。当前仓库只提供可执行的部署入口，没有替用户操作华为云账号、创建服务器或填写公网地址；这些步骤需要在自己的 CodeArts/云主机环境中完成。

## 本地或云主机启动

在项目根目录执行：

~~~powershell
docker compose up -d --build
Invoke-WebRequest http://127.0.0.1:8000/api/health
~~~

首次启动会构建 Vue 静态资源，并由 FastAPI 同时提供 API 与前端页面。应用会自动把镜像内的 `cvf_pre2022.csv` 和 `cvf_2022_2025_full.csv` 导入 SQLite，约包含 25,773 篇论文；本地实测初始化约 90 秒，云服务器耗时取决于磁盘性能。后续启动检测到数据库非空后会跳过导入。整个初始化过程不需要进入容器执行 Shell。SQLite 文件和 CVF 爬取缓存位于 `cvinsight-data` Docker volume 中。

## 华为云 CodeArts 操作边界

1. 将仓库导入 CodeArts，默认分支使用 main，构建分支使用 dev。
2. 构建任务使用仓库根目录的 Dockerfile 构建镜像，并将容器端口 8000 映射到云主机端口；即使不使用 Compose，镜像也会保留首次自动导入配置。
3. 在 CodeArts/云主机环境变量中按需填写 CVINSIGHT_CORS_ORIGINS，不要把真实密钥写入仓库；Docker 默认直接使用 CVF 网站进行缺失论文检索。
4. 在安全组中只开放实际需要的入口；对外提供服务时，推荐由 HTTPS 反向代理转发到容器的 8000 端口。
5. 发布后访问 /api/health，再访问 / 检查前端静态资源；最后用一条 CSV 演示数据验证导入链路。

## 上线前检查

- docker compose config 可以解析 compose 文件。
- /api/health 返回 {"status":"ok"}。
- CVINSIGHT_DATABASE_URL 指向持久化卷，而不是容器临时目录。
- 首次启动完成后，`/api/papers` 应能返回自动导入的论文记录。
- 本地没有匹配论文时，在线检索应从 CVF 网站返回摘要、关键词和原文链接。
- 云端公网地址、构建编号和截图应补写到作业博客，不能用本地地址替代部署证据。
