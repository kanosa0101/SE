from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Keyword, Paper, PaperKeyword
from app.schemas import QualityAudit, TopicInspector, YearlyEvolution
from app.services.keywords import normalize_keyword
from app.services.metrics import build_cooccurrence_graph, build_quality_audit, build_topic_inspector, build_yearly_evolution, calculate_heat

router = APIRouter(prefix="/api/stats", tags=["statistics"])


def _paper_conditions(conference: str | None, year_from: int | None, year_to: int | None):
    conditions = []
    if conference:
        conditions.append(Paper.conference == conference)
    if year_from:
        conditions.append(Paper.year >= year_from)
    if year_to:
        conditions.append(Paper.year <= year_to)
    return conditions


def _keyword_rows(
    db: Session,
    conference: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> list[dict]:
    statement = (
        select(PaperKeyword.paper_id, Keyword.name, Paper.title, Paper.authors, Paper.abstract, Paper.conference, Paper.year, Paper.source, Paper.source_url)
        .join(Keyword, Keyword.id == PaperKeyword.keyword_id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(*_paper_conditions(conference, year_from, year_to))
    )
    return [
        {"paper_id": paper_id, "keyword": keyword, "title": title, "authors": authors, "abstract": abstract, "conference": venue, "year": year, "source": source, "source_url": source_url}
        for paper_id, keyword, title, authors, abstract, venue, year, source, source_url in db.execute(statement).all()
    ]


@router.get("/overview")
def overview(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> dict:
    conditions = _paper_conditions(conference, year_from, year_to)
    total = db.scalar(select(func.count(Paper.id)).where(*conditions)) or 0
    conference_count = db.scalar(select(func.count(distinct(Paper.conference))).where(*conditions)) or 0
    year_min = db.scalar(select(func.min(Paper.year)).where(*conditions))
    year_max = db.scalar(select(func.max(Paper.year)).where(*conditions))
    by_conference = db.execute(
        select(Paper.conference, func.count(Paper.id)).where(*conditions).group_by(Paper.conference)
    ).all()
    return {
        "total_papers": total,
        "conference_count": conference_count,
        "year_from": year_min,
        "year_to": year_max,
        "by_conference": [{"conference": name, "count": count} for name, count in by_conference],
    }


@router.get("/topics")
def topics(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = _keyword_rows(db, conference, year_from, year_to)
    total = db.scalar(select(func.count(Paper.id)).where(*_paper_conditions(conference, year_from, year_to))) or 0
    by_keyword: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_keyword[row["keyword"]].append(row)
    result = []
    for keyword, keyword_rows in by_keyword.items():
        result.append(
            {
                "keyword": keyword,
                "papers": len({row["paper_id"] for row in keyword_rows}),
                "heat": calculate_heat(keyword_rows, total),
            }
        )
    return sorted(result, key=lambda item: (-item["heat"], item["keyword"]))[:10]


@router.get("/graph")
def graph(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> dict:
    return build_cooccurrence_graph(_keyword_rows(db, conference, year_from, year_to))


@router.get("/trends")
def trends(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> dict:
    rows = _keyword_rows(db, conference, year_from, year_to)
    totals: dict[tuple[str, int], int] = {}
    for row in rows:
        key = (row["conference"], row["year"])
        if key not in totals:
            totals[key] = db.scalar(
                select(func.count(Paper.id)).where(Paper.conference == key[0], Paper.year == key[1])
            ) or 0
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["keyword"], row["conference"], row["year"])].append(row)
    series_map: dict[str, list[dict]] = defaultdict(list)
    for (keyword, venue, year), keyword_rows in grouped.items():
        series_map[keyword].append(
            {
                "conference": venue,
                "year": year,
                "heat": calculate_heat(keyword_rows, totals[(venue, year)]),
            }
        )
    years = sorted({row["year"] for row in rows})
    return {
        "years": years,
        "series": [
            {"keyword": keyword, "data": sorted(data, key=lambda item: (item["year"], item["conference"]))}
            for keyword, data in sorted(series_map.items())
        ],
    }





@router.get("/topics/{keyword}/inspector", response_model=TopicInspector)
def topic_inspector(keyword: str, db: Session = Depends(get_db)) -> TopicInspector:
    normalized = normalize_keyword(keyword)
    all_rows = _keyword_rows(db)
    rows = [row for row in all_rows if row["keyword"] == normalized]
    if not rows:
        raise HTTPException(status_code=404, detail="主题不存在")
    total = db.scalar(select(func.count(Paper.id))) or 0
    return build_topic_inspector(rows, normalized, total, all_rows)


@router.get("/evolution", response_model=YearlyEvolution)
def evolution(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)) -> YearlyEvolution:
    return build_yearly_evolution(_keyword_rows(db), limit)


@router.get("/quality", response_model=QualityAudit)
def quality(db: Session = Depends(get_db)) -> QualityAudit:
    papers = db.scalars(select(Paper).order_by(Paper.id)).all()
    rows = [{"abstract": paper.abstract, "authors": paper.authors, "source_url": paper.source_url, "source": paper.source, "conference": paper.conference, "year": paper.year, "keywords": paper.paper_keywords} for paper in papers]
    return build_quality_audit(rows)
