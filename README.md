# CVInsight：顶会论文热词统计平台

## 项目介绍

CVInsight 面向计算机视觉领域论文分析，支持 CVPR、ICCV、ECCV 论文数据的采集、管理和统计。系统提供论文查询、Top 10 热门研究方向、关键词关系图、年度热词演变和趋势分析等功能。

项目采用 Vue 3 + FastAPI + SQLite 实现，爬虫模块负责获取和清洗 CVF 公开论文元数据，后端提供统计接口，前端负责页面交互和可视化展示。

## 部署信息

### Docker Compose 部署

项目根目录执行：

```powershell
docker compose up -d --build
```

启动后访问：

```text
http://localhost:8000
```

查看服务状态：

```powershell
docker compose ps
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

停止服务：

```powershell
docker compose down
```

### 本地开发部署

后端：

```powershell
Set-Location backend
python -m venv .venv
& .venv/Scripts/Activate.ps1
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8000
```

前端另开终端运行：

```powershell
Set-Location frontend
npm ci
npm run dev
```

开发环境访问 `http://localhost:5173`。生产构建可先在 `frontend` 目录执行 `npm run build`，再由 FastAPI 启动后端服务。
