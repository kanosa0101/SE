import io

from app.db import init_db, make_engine, session_factory
from app.services.papers import import_csv


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


def test_paper_list_can_filter_all_papers_in_a_research_area(client):
    for index, keywords in enumerate((["diffusion"], ["generative"]), start=1):
        response = client.post(
            "/api/papers",
            json=paper_payload(f"Area Paper {index}") | {"keywords": keywords},
        )
        assert response.status_code == 201

    response = client.get(
        "/api/papers",
        params={
            "keyword": "Diffusion & Generative Models",
            "keyword_scope": "area",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2


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


def test_csv_import_commits_valid_rows_as_one_batch(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'batch.db'}")
    init_db(engine)
    session = session_factory(engine)()
    commits = 0
    original_commit = session.commit

    def counted_commit():
        nonlocal commits
        commits += 1
        original_commit()

    monkeypatch.setattr(session, "commit", counted_commit)
    content = (
        b"title,conference,year,keywords\n"
        b"Batch Paper 1,CVPR,2024,detection\n"
        b"Batch Paper 2,ICCV,2023,segmentation\n"
        b"Batch Paper 3,ECCV,2022,transformer\n"
    )

    summary = import_csv(session, content)

    assert summary.created == 3
    assert summary.errors == 0
    assert commits == 1
    session.close()


def test_strict_csv_import_flushes_the_batch_once(tmp_path, monkeypatch):
    engine = make_engine(f"sqlite:///{tmp_path / 'strict.db'}")
    init_db(engine)
    session = session_factory(engine)()
    flushes = 0
    original_flush = session.flush

    def counted_flush(*args, **kwargs):
        nonlocal flushes
        flushes += 1
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(session, "flush", counted_flush)
    content = (
        b"title,conference,year,keywords\n"
        b"Strict Paper 1,CVPR,2024,detection\n"
        b"Strict Paper 2,ICCV,2023,segmentation\n"
        b"Strict Paper 3,ECCV,2022,transformer\n"
    )

    summary = import_csv(session, content, strict=True)

    assert summary.created == 3
    assert flushes <= 1
    session.close()


def test_lookup_without_configured_source_returns_explainable_error(client, monkeypatch):
    from app.api import papers as papers_api
    from app.config import Settings, get_settings
    from app.main import app
    from app.services.lookup import LookupUnavailableError

    def unavailable(*args, **kwargs):
        raise LookupUnavailableError("CVF 网站在线检索暂时不可用")

    monkeypatch.setattr(papers_api, "lookup_cvf_title", unavailable, raising=False)
    app.dependency_overrides[get_settings] = lambda: Settings(lookup_url=None)
    try:
        response = client.get("/api/papers/lookup", params={"title": "Unknown Paper"})
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 502
    assert "CVF" in response.json()["detail"]


def test_lookup_without_external_source_returns_cvf_metadata(client, monkeypatch):
    from app.api import papers as papers_api
    from app.config import Settings, get_settings
    from app.main import app
    from app.schemas import PaperCreate

    expected = PaperCreate(
        title="Cvf Online Paper",
        abstract="Online abstract",
        keywords=["vision-language model"],
        conference="ECCV",
        year=2024,
        source="CVF",
        source_url="https://openaccess.thecvf.com/paper",
    )
    monkeypatch.setattr(papers_api, "lookup_cvf_title", lambda *args, **kwargs: expected, raising=False)
    app.dependency_overrides[get_settings] = lambda: Settings(lookup_url=None)
    try:
        response = client.get("/api/papers/lookup", params={"title": "Cvf Online Paper"})
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json()["abstract"] == "Online abstract"
    assert response.json()["keywords"] == ["vision-language model"]
    assert response.json()["source_url"] == "https://openaccess.thecvf.com/paper"




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
def test_paper_export_respects_year_range(client):
    for year in (2020, 2023, 2025):
        response = client.post(
            "/api/papers",
            json=paper_payload(f"Export Range Paper {year}") | {"year": year},
        )
        assert response.status_code == 201

    response = client.get(
        "/api/papers/export",
        params={"format": "csv", "year_from": 2021, "year_to": 2024},
    )

    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Export Range Paper 2023" in body
    assert "Export Range Paper 2020" not in body
    assert "Export Range Paper 2025" not in body

