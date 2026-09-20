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
