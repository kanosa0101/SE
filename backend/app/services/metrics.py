from collections import Counter, defaultdict
from itertools import combinations


def calculate_heat(rows: list[dict], total_papers: int) -> float:
    if total_papers <= 0:
        return 0.0
    paper_ids = {row["paper_id"] for row in rows}
    return round(len(paper_ids) / total_papers * 1000, 1)


def safe_growth(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def build_cooccurrence_graph(rows: list[dict], max_nodes: int = 50) -> dict[str, list[dict]]:
    paper_keywords: dict[int, set[str]] = defaultdict(set)
    keyword_papers: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        keyword = row["keyword"]
        paper_id = row["paper_id"]
        paper_keywords[paper_id].add(keyword)
        keyword_papers[keyword].add(paper_id)

    ordered_names = sorted(keyword_papers, key=lambda name: (-len(keyword_papers[name]), name))[:max_nodes]
    selected = set(ordered_names)
    nodes = [
        {"name": name, "value": len(keyword_papers[name])}
        for name in ordered_names
    ]
    edge_counts: Counter[tuple[str, str]] = Counter()
    for names in paper_keywords.values():
        edge_counts.update(combinations(sorted(selected.intersection(names)), 2))
    links = [
        {"source": source, "target": target, "value": value}
        for (source, target), value in sorted(edge_counts.items())
    ]
    return {"nodes": nodes, "links": links}


def build_topic_inspector(rows: list[dict], keyword: str, total_papers: int) -> dict:
    ordered_rows = sorted(rows, key=lambda row: (-row["year"], row["paper_id"]))
    return {
        "keyword": keyword,
        "papers": len({row["paper_id"] for row in rows}),
        "heat": calculate_heat(rows, total_papers),
        "representative_papers": [
            {key: row[key] for key in ("paper_id", "title", "authors", "conference", "year", "abstract", "source", "source_url") if key in row}
            for row in ordered_rows
        ],
    }


def build_yearly_evolution(rows: list[dict], limit: int = 10) -> dict:
    years = sorted({row["year"] for row in rows})
    frames = []
    for year in years:
        year_rows = [row for row in rows if row["year"] == year]
        total_papers = len({row["paper_id"] for row in year_rows})
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in year_rows:
            grouped[row["keyword"]].append(row)
        topics = [
            {"keyword": keyword, "papers": len({row["paper_id"] for row in keyword_rows}), "heat": calculate_heat(keyword_rows, total_papers)}
            for keyword, keyword_rows in grouped.items()
        ]
        topics.sort(key=lambda item: (-item["heat"], item["keyword"]))
        frames.append({"year": year, "topics": topics[:limit]})
    return {"years": years, "frames": frames}


def build_quality_audit(rows: list[dict]) -> dict:
    total = len(rows)
    missing_fields = {field: sum(1 for row in rows if not row.get(field)) for field in ("abstract", "authors", "source_url")}
    keyworded = sum(1 for row in rows if row.get("keywords"))
    return {
        "total": total,
        "keyword_coverage": round(keyworded / total * 100, 1) if total else 0.0,
        "missing_fields": missing_fields,
    }
