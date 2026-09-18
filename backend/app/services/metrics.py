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
