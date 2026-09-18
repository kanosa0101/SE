from fastapi import FastAPI

from app import models  # noqa: F401  # register SQLAlchemy metadata
from app.api.papers import router as papers_router
from app.api.stats import router as stats_router
from app.db import get_db, init_db, runtime_engine


app = FastAPI(title="CVInsight API")
app.include_router(papers_router)
app.include_router(stats_router)


@app.on_event("startup")
def initialize_database() -> None:
    init_db(runtime_engine)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
