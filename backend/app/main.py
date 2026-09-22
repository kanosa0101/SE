from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  # register SQLAlchemy metadata
from app.api.papers import router as papers_router
from app.api.stats import router as stats_router
from app.config import get_settings
from app.db import get_db, init_db, runtime_engine
from app.services.bootstrap import bootstrap_database


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(runtime_engine)
    files = [Path(item.strip()) for item in settings.bootstrap_files.split(",") if item.strip()]
    bootstrap_database(runtime_engine, files)
    yield


app = FastAPI(title="CVInsight API", lifespan=lifespan)
cors_origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(papers_router)
app.include_router(stats_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = Path(settings.frontend_dist).resolve()
assets_dir = frontend_dist / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def serve_frontend(path: str):
    if not frontend_dist.is_dir():
        return Response(status_code=404)
    requested = (frontend_dist / path).resolve()
    try:
        requested.relative_to(frontend_dist)
    except ValueError:
        return Response(status_code=404)
    if requested.is_file():
        return FileResponse(requested)
    index_file = frontend_dist / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return Response(status_code=404)

