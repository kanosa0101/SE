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


def test_csv_import_preserves_cvf_provenance(client):
    csv_data = io.BytesIO(
        b"title,conference,year,source,source_url,parser_version,crawled_at\n"
        b"CVF Paper,CVPR,2024,cvf,https://openaccess.thecvf.com/paper.pdf,cvf-v2,2026-09-18T12:34:56Z\n"
    )

    response = client.post(
        "/api/papers/import",
        files={"file": ("papers.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["created"] == 1

    papers = client.get("/api/papers").json()["items"]
    assert papers[0]["source"] == "cvf"
    assert papers[0]["source_url"] == "https://openaccess.thecvf.com/paper.pdf"
    assert papers[0]["parser_version"] == "cvf-v2"
    assert papers[0]["crawled_at"] == "2026-09-18T12:34:56Z"

def test_crawled_at_offset_is_normalized_to_utc(client):
    response = client.post(
        "/api/papers",
        json=paper_payload("Offset Timestamp Paper") | {"crawled_at": "2026-09-18T14:34:56+02:00"},
    )

    assert response.status_code == 201
    assert response.json()["crawled_at"] == "2026-09-18T12:34:56Z"


def test_csv_import_rejects_malformed_crawled_at(client):
    csv_data = io.BytesIO(
        b"title,conference,year,crawled_at\n"
        b"Malformed Timestamp,CVPR,2024,not-a-timestamp\n"
    )

    response = client.post(
        "/api/papers/import",
        files={"file": ("papers.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["errors"] == 1
    assert "invalid crawled_at timestamp" in response.json()["items"][0]["message"]


def test_lookup_without_configured_source_returns_explainable_error(client):
    response = client.get("/api/papers/lookup", params={"title": "Unknown Paper"})

    assert response.status_code == 502
    assert "未配置" in response.json()["detail"]




def test_paper_year_range_filter(client):
    for year in (2020, 2023, 2025):
        response = client.post(
            "/api/papers",
            json=paper_payload(f"Range Paper {year}") | {"year": year},
        )
        assert response.status_code == 201

    response = client.get("/api/papers", params={"year_from": 2021, "year_to": 2024})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["year"] == 2023

