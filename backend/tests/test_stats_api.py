from app.api import stats as stats_api


def seed_papers(client):
    client.post(
        "/api/papers",
        json={
            "title": "Diffusion Vision",
            "conference": "CVPR",
            "year": 2024,
            "abstract": "diffusion generation",
            "keywords": ["diffusion", "generation"],
            "source": "demo",
        },
    )
    client.post(
        "/api/papers",
        json={
            "title": "Vision Language Study",
            "conference": "ECCV",
            "year": 2024,
            "abstract": "vision language model",
            "keywords": ["VLM"],
            "source": "demo",
        },
    )


def test_overview_returns_counts(client):
    seed_papers(client)

    response = client.get("/api/stats/overview")

    assert response.status_code == 200
    assert response.json()["total_papers"] == 2
    assert response.json()["conference_count"] == 2


def test_topics_graph_and_trends_return_structured_statistics(client):
    seed_papers(client)

    topics = client.get("/api/stats/topics")
    graph = client.get("/api/stats/graph")
    trends = client.get("/api/stats/trends", params={"conference": "CVPR"})

    assert topics.status_code == graph.status_code == trends.status_code == 200
    assert len(topics.json()) <= 10
    assert {node["name"] for node in graph.json()["nodes"]}
    assert trends.json()["series"]


def test_graph_keeps_the_keyword_node_count_compact(client):
    for index in range(40):
        response = client.post(
            "/api/papers",
            json={
                "title": f"Graph Topic Paper {index}",
                "conference": "CVPR",
                "year": 2024,
                "abstract": f"topic-{index}",
                "keywords": [f"topic-{index}"],
                "source": "demo",
            },
        )
        assert response.status_code == 201

    response = client.get("/api/stats/graph")

    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 32


def test_topics_ranks_research_areas_not_raw_words(client):
    client.post(
        "/api/papers",
        json={
            "title": "Generic Carrier Study",
            "conference": "CVPR",
            "year": 2024,
            "abstract": "model",
            "keywords": ["model", "segmentation"],
            "source": "demo",
        },
    )

    response = client.get("/api/stats/topics")

    assert response.status_code == 200
    areas = [topic["keyword"] for topic in response.json()]
    # 泛化载体词不进入榜单，关键词聚合为研究领域
    assert "model" not in areas
    assert "Segmentation" in areas
    assert all(area not in ("image", "data", "learning") for area in areas)


def test_trends_returns_top_research_areas_by_coverage(client):
    seed_papers(client)
    for index in range(3):
        client.post(
            "/api/papers",
            json={
                "title": f"Segmentation Study {index}",
                "conference": "CVPR",
                "year": 2024,
                "abstract": "segmentation",
                "keywords": ["segmentation"],
                "source": "demo",
            },
        )
    client.post(
        "/api/papers",
        json={
            "title": "Aardvark Tracking",
            "conference": "CVPR",
            "year": 2024,
            "abstract": "tracking",
            "keywords": ["aardvark"],
            "source": "demo",
        },
    )

    response = client.get("/api/stats/trends", params={"conference": "CVPR", "limit": 1})

    assert response.status_code == 200
    areas = [series["keyword"] for series in response.json()["series"]]
    assert areas == ["Segmentation"]


def test_topic_inspector_aggregates_a_research_area_when_requested(client):
    for index in range(1, 3):
        response = client.post(
            "/api/papers",
            json={
                "title": f"Diffusion Area Paper {index}",
                "conference": "CVPR",
                "year": 2024,
                "abstract": "generative vision",
                "keywords": ["diffusion", "generative"],
                "source": "demo",
            },
        )
        assert response.status_code == 201

    response = client.get(
        "/api/stats/topics/Diffusion%20%26%20Generative%20Models/inspector",
        params={"scope": "area"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["keyword"] == "Diffusion & Generative Models"
    assert body["papers"] == 2
    assert body["year_series"] == [{"year": 2024, "papers": 2}]
    assert len(body["representative_papers"]) == 2
    assert {paper["title"] for paper in body["representative_papers"]} == {
        "Diffusion Area Paper 1",
        "Diffusion Area Paper 2",
    }


def test_topic_inspector_does_not_load_the_full_keyword_table(client, monkeypatch):
    seed_papers(client)

    def fail_if_full_table_is_loaded(*_args, **_kwargs):
        raise AssertionError("topic inspector should query related rows only")

    monkeypatch.setattr(stats_api, "_keyword_rows", fail_if_full_table_is_loaded)

    response = client.get("/api/stats/topics/diffusion/inspector")

    assert response.status_code == 200
    assert response.json()["related_keywords"]


def test_topic_inspector_limits_related_keyword_payload(client):
    response = client.post(
        "/api/papers",
        json={
            "title": "Anchor Topic Paper",
            "conference": "CVPR",
            "year": 2024,
            "abstract": "anchor",
            "keywords": ["anchor"] + [f"related-{index}" for index in range(12)],
            "source": "demo",
        },
    )
    assert response.status_code == 201

    response = client.get("/api/stats/topics/anchor/inspector")

    assert response.status_code == 200
    assert len(response.json()["related_keywords"]) == 8
