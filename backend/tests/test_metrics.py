from app.services.metrics import (
    build_cooccurrence_graph,
    calculate_heat,
    safe_growth,
)


def test_heat_uses_paper_coverage_not_raw_token_count():
    rows = [
        {"keyword": "diffusion", "conference": "CVPR", "year": 2024, "paper_id": 1},
        {"keyword": "diffusion", "conference": "CVPR", "year": 2024, "paper_id": 2},
    ]

    assert calculate_heat(rows, total_papers=4) == 500.0


def test_growth_is_undefined_when_previous_heat_is_zero():
    assert safe_growth(10.0, 0.0) is None
    assert safe_growth(15.0, 10.0) == 50.0


def test_graph_contains_keyword_pair_that_cooccurs_in_one_paper():
    rows = [
        {"paper_id": 1, "keyword": "diffusion"},
        {"paper_id": 1, "keyword": "generation"},
        {"paper_id": 2, "keyword": "diffusion"},
    ]

    graph = build_cooccurrence_graph(rows)

    assert {node["name"] for node in graph["nodes"]} == {"diffusion", "generation"}
    assert graph["links"] == [{"source": "diffusion", "target": "generation", "value": 1}]
