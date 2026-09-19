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


def test_topics_excludes_generic_carrier_words(client):
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
    keywords = [topic["keyword"] for topic in response.json()]
    assert "model" not in keywords
    assert "segmentation" in keywords


def test_trends_returns_top_keywords_by_coverage_not_alphabetical(client):
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
    keywords = [series["keyword"] for series in response.json()["series"]]
    assert keywords == ["segmentation"]
