from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, distinct, func, select
from sqlalchemy.orm import Session, aliased

from app.db import get_db
from app.models import Keyword, Paper, PaperKeyword
from app.schemas import QualityAudit, TopicInspector, YearlyEvolution
from app.services.keywords import is_informative_keyword, normalize_keyword
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
    detail: bool = False,
) -> list[dict]:
    # 统计端点只需要 id 维度字段；详情字段（标题/作者/摘要）只有主题检查器需要。
    columns = (
        (Paper.title, Paper.authors, Paper.abstract, Paper.source, Paper.source_url) if detail else ()
    )
    statement = (
        select(PaperKeyword.paper_id, Keyword.name, Paper.conference, Paper.year, *columns)
        .join(Keyword, Keyword.id == PaperKeyword.keyword_id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(*_paper_conditions(conference, year_from, year_to))
    )
    if detail:
        return [
            {"paper_id": paper_id, "keyword": keyword, "title": title, "authors": authors, "abstract": abstract, "conference": venue, "year": year, "source": source, "source_url": source_url}
            for paper_id, keyword, title, authors, abstract, venue, year, source, source_url in db.execute(statement).all()
        ]
    return [
        {"paper_id": paper_id, "keyword": keyword, "conference": venue, "year": year}
        for paper_id, keyword, venue, year in db.execute(statement).all()
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
        if not is_informative_keyword(row["keyword"]):
            continue
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


def _cooccurrence_graph_sql(db: Session, conference: str | None, year_from: int | None, year_to: int | None) -> dict:
    """SQL 聚合版共现图谱：组合计数交给 SQLite 自连接，避免全量行拉回 Python 统计。"""
    conditions = _paper_conditions(conference, year_from, year_to)
    top = db.execute(
        select(Keyword.name, func.count(distinct(PaperKeyword.paper_id)).label("papers"))
        .join(PaperKeyword, PaperKeyword.keyword_id == Keyword.id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(*conditions)
        .group_by(Keyword.name)
        .order_by(desc("papers"), Keyword.name)
        .limit(50)
    ).all()
    if not top:
        return {"nodes": [], "links": []}
    name_to_id = dict(db.execute(select(Keyword.name, Keyword.id)).all())
    top_ids = [name_to_id[name] for name, _ in top]
    pk1, pk2 = aliased(PaperKeyword), aliased(PaperKeyword)
    k1, k2 = aliased(Keyword), aliased(Keyword)
    pairs = db.execute(
        select(k1.name, k2.name, func.count())
        .select_from(pk1)
        .join(pk2, (pk2.paper_id == pk1.paper_id) & (pk2.keyword_id > pk1.keyword_id))
        .join(k1, k1.id == pk1.keyword_id)
        .join(k2, k2.id == pk2.keyword_id)
        .join(Paper, Paper.id == pk1.paper_id)
        .where(pk1.keyword_id.in_(top_ids), pk2.keyword_id.in_(top_ids), *conditions)
        .group_by(k1.name, k2.name)
    ).all()
    edge_counts: Counter[tuple[str, str]] = Counter()
    for first, second, value in pairs:
        edge_counts[(first, second) if first < second else (second, first)] += value
    return {
        "nodes": [{"name": name, "value": papers} for name, papers in top],
        "links": [
            {"source": source, "target": target, "value": value}
            for (source, target), value in sorted(edge_counts.items())
        ],
    }


@router.get("/graph")
def graph(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> dict:
    return _cooccurrence_graph_sql(db, conference, year_from, year_to)


@router.get("/trends")
def trends(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    limit: int = Query(default=10, ge=1, le=50),
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
    # 只保留覆盖论文数最高且具备方向信息量的关键词，避免泛化载体词淹没图表。
    keyword_papers: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if not is_informative_keyword(row["keyword"]):
            continue
        keyword_papers[row["keyword"]].add(row["paper_id"])
    top_keywords = {
        keyword
        for keyword, _ in sorted(keyword_papers.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]
    }
    grouped: dict[tuple[str, str, int], list[dict]] = defaultdict(list)
    for row in rows:
        if row["keyword"] not in top_keywords:
            continue
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
    ranked = sorted(
        series_map.items(),
        key=lambda item: (-len(keyword_papers[item[0]]), item[0]),
    )
    return {
        "years": years,
        "series": [
            {"keyword": keyword, "data": sorted(data, key=lambda item: (item["year"], item["conference"]))}
            for keyword, data in ranked
        ],
    }





@router.get("/topics/{keyword}/inspector", response_model=TopicInspector)
def topic_inspector(keyword: str, db: Session = Depends(get_db)) -> TopicInspector:
    normalized = normalize_keyword(keyword)
    all_rows = _keyword_rows(db)
    statement = (
        select(PaperKeyword.paper_id, Keyword.name, Paper.title, Paper.authors, Paper.abstract, Paper.conference, Paper.year, Paper.source, Paper.source_url)
        .join(Keyword, Keyword.id == PaperKeyword.keyword_id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(Keyword.name == normalized)
    )
    rows = [
        {"paper_id": paper_id, "keyword": keyword, "title": title, "authors": authors, "abstract": abstract, "conference": venue, "year": year, "source": source, "source_url": source_url}
        for paper_id, keyword, title, authors, abstract, venue, year, source, source_url in db.execute(statement).all()
    ]
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
