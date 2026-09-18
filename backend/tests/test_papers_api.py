import io


def paper_payload(title="A Test Vision Paper"):
    return {
        "title": title,
        "conference": "CVPR",
        "year": 2024,
        "abstract": "diffusion vision",
        "authors": "Researcher One",
        "keywords": ["Diffusion Models"],
        "source": "demo",
        "source_url": "https://example.test/paper",
    }


def test_paper_create_and_exact_title_search(client):
    created = client.post("/api/papers", json=paper_payload())
    assert created.status_code == 201
    assert created.json()["keywords"] == ["diffusion model"]

    response = client.get("/api/papers", params={"q": "A Test Vision Paper"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_paper_update_and_delete(client):
    created = client.post("/api/papers", json=paper_payload())
    paper_id = created.json()["id"]

    updated = client.put(
        f"/api/papers/{paper_id}",
        json={"title": "Updated Vision Paper", "keywords": ["VLM"]},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated Vision Paper"
    assert updated.json()["keywords"] == ["vision-language model"]

    deleted = client.delete(f"/api/papers/{paper_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_csv_import_reports_created_and_invalid_rows(client):
    csv_data = io.BytesIO(
        b"title,conference,year,abstract,keywords,source_url\n"
        b"Imported Paper,CVPR,2023,vision abstract,detection|segmentation,https://example.test/1\n"
        b"Broken Paper,INVALID,2023,broken,,https://example.test/2\n"
    )
    response = client.post(
        "/api/papers/import",
        files={"file": ("papers.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["errors"] == 1


def test_lookup_without_configured_source_returns_explainable_error(client):
    response = client.get("/api/papers/lookup", params={"title": "Unknown Paper"})

    assert response.status_code == 502
    assert "未配置" in response.json()["detail"]
