from collections import Counter, defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, distinct, func, select
from sqlalchemy.orm import Session, aliased

from app.db import get_db
from app.models import Keyword, Paper, PaperKeyword
from app.schemas import QualityAudit, TopicInspector, YearlyEvolution
from app.services.keywords import canonical_research_area, normalize_keyword, research_area_for
from app.services.metrics import build_topic_inspector, calculate_heat

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


def _area_rows(db: Session, conference: str | None = None, year_from: int | None = None, year_to: int | None = None):
    """按元组流返回 (关键词名, 会议, 年份, paper_id)，供领域聚合复用。

    25k+ 记录下构建 25 万个 dict 的开销显著，这里保持原始元组，
    领域映射结果按关键词名缓存，避免逐行重复计算。
    """
    statement = (
        select(Keyword.name, Paper.conference, Paper.year, PaperKeyword.paper_id)
        .select_from(PaperKeyword)
        .join(Keyword, Keyword.id == PaperKeyword.keyword_id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(*_paper_conditions(conference, year_from, year_to))
    )
    area_cache: dict[str, str | None] = {}

    def area_of(name: str) -> str | None:
        if name not in area_cache:
            area_cache[name] = research_area_for(name)
        return area_cache[name]

    return db.execute(statement).all(), area_of


def _area_totals(db: Session, conference: str | None = None, year_from: int | None = None, year_to: int | None = None) -> dict[tuple[str, int], int]:
    """每个 (会议, 年份) 的论文总数，供各口径计算覆盖率。"""
    conditions = _paper_conditions(conference, year_from, year_to)
    statement = select(Paper.conference, Paper.year, func.count(Paper.id)).where(*conditions).group_by(Paper.conference, Paper.year)
    return {(venue, year): count for venue, year, count in db.execute(statement).all()}


@router.get("/topics")
def topics(
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year_from: int | None = Query(default=None, ge=1990, le=2100),
    year_to: int | None = Query(default=None, ge=1990, le=2100),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows, area_of = _area_rows(db, conference, year_from, year_to)
    total = db.scalar(select(func.count(Paper.id)).where(*_paper_conditions(conference, year_from, year_to))) or 0
    # 作业口径是"热门领域/研究方向"而非出现最多的词：先把关键词映射到研究领域，
    # 再按领域的覆盖论文数（并集去重）排序；未映射的泛化载体词不参与排名。
    area_papers: dict[str, set[int]] = defaultdict(set)
    for name, _venue, _year, paper_id in rows:
        area = area_of(name)
        if area is not None:
            area_papers[area].add(paper_id)
    result = [
        {
            "keyword": area,
            "papers": len(papers),
            "heat": round(len(papers) / total * 1000, 1) if total else 0.0,
        }
        for area, papers in area_papers.items()
    ]
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
    rows, area_of = _area_rows(db, conference, year_from, year_to)
    totals = _area_totals(db, conference, year_from, year_to)
    # 趋势与 Top 10 同口径：按研究领域聚合（覆盖论文数并集去重），未映射词不参与。
    area_papers: dict[str, set[int]] = defaultdict(set)
    grouped: dict[tuple[str, str, int], set[int]] = defaultdict(set)
    for name, venue, year, paper_id in rows:
        area = area_of(name)
        if area is None:
            continue
        area_papers[area].add(paper_id)
        grouped[(area, venue, year)].add(paper_id)
    top_areas = {
        area
        for area, _ in sorted(area_papers.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]
    }
    series_map: dict[str, list[dict]] = defaultdict(list)
    for (area, venue, year), paper_ids in grouped.items():
        if area not in top_areas:
            continue
        series_map[area].append(
            {
                "conference": venue,
                "year": year,
                "heat": calculate_heat([{"paper_id": pid} for pid in paper_ids], totals.get((venue, year), 0)),
            }
        )
    years = sorted({year for (_venue, year), _count in totals.items()}) if totals else []
    ranked = sorted(
        series_map.items(),
        key=lambda item: (-len(area_papers[item[0]]), item[0]),
    )
    return {
        "years": years,
        "series": [
            {"keyword": area, "data": sorted(data, key=lambda item: (item["year"], item["conference"]))}
            for area, data in ranked
        ],
    }





@router.get("/topics/{keyword}/inspector", response_model=TopicInspector)
def topic_inspector(
    keyword: str,
    scope: Literal["keyword", "area"] = Query(default="keyword"),
    db: Session = Depends(get_db),
) -> TopicInspector:
    normalized = normalize_keyword(keyword)
    all_rows = _keyword_rows(db)
    display_name = normalized
    keyword_names = [normalized]
    if scope == "area":
        display_name = canonical_research_area(normalized) or ""
        if display_name:
            keyword_names = [
                name
                for (name,) in db.execute(select(Keyword.name)).all()
                if research_area_for(name) == display_name
            ]
    statement = (
        select(PaperKeyword.paper_id, Keyword.name, Paper.title, Paper.authors, Paper.abstract, Paper.conference, Paper.year, Paper.source, Paper.source_url)
        .join(Keyword, Keyword.id == PaperKeyword.keyword_id)
        .join(Paper, Paper.id == PaperKeyword.paper_id)
        .where(Keyword.name.in_(keyword_names))
    )
    rows = [
        {"paper_id": paper_id, "keyword": keyword, "title": title, "authors": authors, "abstract": abstract, "conference": venue, "year": year, "source": source, "source_url": source_url}
        for paper_id, keyword, title, authors, abstract, venue, year, source, source_url in db.execute(statement).all()
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="主题不存在")
    total = db.scalar(select(func.count(Paper.id))) or 0
    return build_topic_inspector(rows, display_name, total, all_rows)


@router.get("/evolution", response_model=YearlyEvolution)
def evolution(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)) -> YearlyEvolution:
    rows, area_of = _area_rows(db)
    totals = _area_totals(db)
    # 与 Top 10 / 趋势同口径：按研究领域聚合，未映射的泛化词不参与。
    area_papers: dict[str, set[int]] = defaultdict(set)
    grouped: dict[tuple[str, int], set[int]] = defaultdict(set)
    for name, _venue, year, paper_id in rows:
        area = area_of(name)
        if area is None:
            continue
        area_papers[area].add(paper_id)
        grouped[(area, year)].add(paper_id)
    top_areas = {
        area
        for area, _ in sorted(area_papers.items(), key=lambda item: (-len(item[1]), item[0]))[:limit]
    }
    years = sorted({year for (_venue, year), _count in totals.items()}) if totals else []
    papers_per_year = defaultdict(int)
    for (_venue, year), count in totals.items():
        papers_per_year[year] += count
    grouped_by_year: dict[int, list[tuple[str, set[int]]]] = defaultdict(list)
    for (area, year), paper_ids in grouped.items():
        if area in top_areas:
            grouped_by_year[year].append((area, paper_ids))
    frames = []
    for year in years:
        frame_topics = [
            {"keyword": area, "papers": len(paper_ids), "heat": calculate_heat([{"paper_id": pid} for pid in paper_ids], papers_per_year.get(year, 0))}
            for area, paper_ids in grouped_by_year.get(year, [])
        ]
        frame_topics.sort(key=lambda item: (-item["heat"], item["keyword"]))
        frames.append({"year": year, "topics": frame_topics[:limit]})
    return {"years": years, "frames": frames}


@router.get("/quality", response_model=QualityAudit)
def quality(db: Session = Depends(get_db)) -> QualityAudit:
    # 全部用聚合查询：逐 ORM 对象懒加载关键词在 12k+ 记录下是 N+1，会拖垮页面切换。
    total = db.scalar(select(func.count(Paper.id))) or 0
    keyworded = db.scalar(select(func.count(distinct(PaperKeyword.paper_id)))) or 0
    missing = {
        field: db.scalar(
            select(func.count(Paper.id)).where(
                func.coalesce(getattr(Paper, field), "") == ""
            )
        ) or 0
        for field in ("abstract", "authors", "source_url")
    }
    source_counts = dict(db.execute(select(Paper.source, func.count(Paper.id)).group_by(Paper.source)).all())
    matrix = db.execute(
        select(Paper.conference, Paper.year, func.count(Paper.id)).group_by(Paper.conference, Paper.year)
    ).all()
    return QualityAudit(
        total=total,
        keyword_coverage=round(keyworded / total * 100, 1) if total else 0.0,
        missing_fields=missing,
        source_breakdown=sorted(
            (
                {"source": (source or "unknown").strip() or "unknown", "papers": count}
                for source, count in source_counts.items()
            ),
            key=lambda item: item["source"],
        ),
        conference_year_matrix=[
            {"conference": conference, "year": year, "papers": count}
            for conference, year, count in sorted(matrix, key=lambda item: (item[0], item[1]))
        ],
    )
