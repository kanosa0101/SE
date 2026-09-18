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
