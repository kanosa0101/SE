import csv
import io


def seed_transformer_papers(client):
    first = client.post(
        "/api/papers",
        json={
            "title": "Transformer Vision",
            "conference": "CVPR",
            "year": 2024,
            "authors": "Alice Smith, Bob Lee",
            "abstract": "A transformer model for vision.",
            "keywords": ["Transformer", "Attention"],
            "source": "cvf",
            "source_url": "https://example.test/transformer",
        },
    )
    second = client.post(
        "/api/papers",
        json={
            "title": "Older Transformer Study",
            "conference": "CVPR",
            "year": 2022,
            "authors": "Carol Jones",
            "abstract": "An older transformer study.",
            "keywords": ["Transformer"],
            "source": "cvf",
        },
    )
    assert first.status_code == second.status_code == 201


def test_topic_inspector_returns_keyword_and_representative_papers(client):
    seed_transformer_papers(client)

    response = client.get("/api/stats/topics/transformer/inspector")

    assert response.status_code == 200
    body = response.json()
    assert body["keyword"] == "transformer"
    assert body["representative_papers"]
    assert body["representative_papers"][0]["year"] == 2024
    assert body["conference_breakdown"] == [{"conference": "CVPR", "papers": 2}]
    assert body["year_series"] == [
        {"year": 2022, "papers": 1},
        {"year": 2024, "papers": 1},
    ]
    assert body["related_keywords"]
    assert body["related_keywords"][0]["keyword"] == "attention"


def test_topic_inspector_normalizes_aliases(client):
    response = client.post(
        "/api/papers",
        json={
            "title": "Vision Language Models",
            "conference": "CVPR",
            "year": 2024,
            "keywords": ["vision-language model"],
        },
    )
    assert response.status_code == 201

    response = client.get("/api/stats/topics/vision language models/inspector")

    assert response.status_code == 200
    assert response.json()["keyword"] == "vision-language model"


def test_topic_inspector_returns_404_for_unknown_keyword(client):
    response = client.get("/api/stats/topics/does-not-exist/inspector")

    assert response.status_code == 404


def test_evolution_sorts_years_and_limits_topics_per_frame(client):
    for index in range(12):
        response = client.post(
            "/api/papers",
            json={
                "title": f"Evolution Paper {index}",
                "conference": "CVPR",
                "year": 2024 - (index % 3),
                "keywords": [f"topic-{index}"],
            },
        )
        assert response.status_code == 201

    response = client.get("/api/stats/evolution", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["years"] == sorted(body["years"])
    assert all(len(frame["topics"]) <= 10 for frame in body["frames"])


def test_evolution_returns_empty_frames_for_empty_dataset(client):
    response = client.get("/api/stats/evolution")

    assert response.status_code == 200
    assert response.json() == {"years": [], "frames": []}


def test_quality_audit_reports_missing_metadata(client):
    response = client.post(
        "/api/papers",
        json={"title": "Incomplete Paper", "conference": "CVPR", "year": 2024},
    )
    assert response.status_code == 201

    audit = client.get("/api/stats/quality")

    assert audit.status_code == 200
    body = audit.json()
    assert body["total"] == 1
    assert "keyword_coverage" in body
    assert body["missing_fields"]["abstract"] == 1
    assert body["missing_fields"]["authors"] == 1
    assert body["missing_fields"]["source_url"] == 1
    assert body["source_breakdown"] == [{"source": "manual", "papers": 1}]
    assert body["conference_year_matrix"] == [{"conference": "CVPR", "year": 2024, "papers": 1}]


def test_quality_audit_labels_blank_source_unknown_and_csv_import(client):
    blank = client.post(
        "/api/papers",
        json={"title": "Blank Source Paper", "conference": "CVPR", "year": 2024, "source": ""},
    )
    assert blank.status_code == 201

    imported = client.post(
        "/api/papers/import",
        files={"file": ("papers.csv", io.BytesIO(b"title,conference,year\nCSV Paper,ECCV,2023\n"), "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["created"] == 1

    audit = client.get("/api/stats/quality")
    assert audit.status_code == 200
    assert audit.json()["source_breakdown"] == [
        {"source": "csv", "papers": 1},
        {"source": "unknown", "papers": 1},
    ]

def test_csv_export_has_stable_header_and_conference_filter(client):
    seed_transformer_papers(client)

    response = client.get("/api/papers/export", params={"format": "csv", "conference": "CVPR"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["title", "authors", "conference", "year", "abstract", "keywords", "source", "source_url"]
    assert len(rows) == 3


def test_bibtex_export_combined_q_and_keyword_filter(client):
    seed_transformer_papers(client)

    response = client.get(
        "/api/papers/export",
        params={"format": "bibtex", "q": "vision", "keyword": "vision"},
    )

    assert response.status_code == 200


def test_bibtex_export_uses_deterministic_keys(client):
    seed_transformer_papers(client)

    response = client.get("/api/papers/export", params={"format": "bibtex", "conference": "CVPR"})

    assert response.status_code == 200
    assert "@inproceedings{Smith2024TransformerVision," in response.text
    assert "@inproceedings{Jones2022OlderTransformerStudy," in response.text


def test_bibtex_export_escapes_latex_sensitive_characters(client):
    response = client.post(
        "/api/papers",
        json={
            "title": "A {B} 50%_& #$^~\\ study\nnext",
            "conference": "CVPR",
            "year": 2024,
            "authors": "A_uthor & Co\\Author",
            "abstract": "Line one\nLine two\r\nLine three",
        },
    )
    assert response.status_code == 201

    response = client.get("/api/papers/export", params={"format": "bibtex"})

    assert response.status_code == 200
    assert r"title = {A \{B\} 50\%\_\& \#\$\^{}\~{}\textbackslash{} study next}," in response.text
    assert r"author = {A\_uthor \& Co\textbackslash{}Author}," in response.text
    assert "abstract = {Line one Line two Line three}," in response.text


def test_export_rejects_unknown_format(client):
    response = client.get("/api/papers/export", params={"format": "json"})

    assert response.status_code == 422
