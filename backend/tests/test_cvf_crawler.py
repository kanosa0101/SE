import hashlib
import json
import time
from pathlib import Path

import httpx

from app.crawlers.cvf import CvfCrawler, CvfRecord, parse_detail, parse_index


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_deduplicates_and_resolves_relative_links() -> None:
    urls = parse_index(read_fixture("cvf_index.html"), "https://openaccess.thecvf.com")

    assert urls == [
        "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html",
        "https://openaccess.thecvf.com/content/CVPR2024/html/Another_Test_Paper_CVPR_2024_paper.html",
    ]


def test_parse_detail_extracts_cvf_metadata() -> None:
    detail_url = "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"

    record = parse_detail(read_fixture("cvf_detail.html"), "CVPR", 2024, detail_url)

    assert record.title == "A Test Paper"
    assert record.authors == "Alice Example and Bob Example"
    assert record.conference == "CVPR"
    assert record.year == 2024
    assert record.abstract == "A concise abstract."
    assert record.source_url == detail_url
    assert record.pdf_url is not None
    assert record.pdf_url.endswith(".pdf")


def test_parse_detail_warns_when_abstract_is_missing() -> None:
    detail_url = "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"
    html = read_fixture("cvf_detail.html").replace(
        '<div id="abstract"> A concise abstract. </div>', ""
    )

    record = parse_detail(html, "CVPR", 2024, detail_url)

    assert record.abstract is None
    assert record.parse_warnings == ["missing_abstract"]


def test_repeated_failed_url_is_reported_in_current_summary(tmp_path: Path) -> None:
    detail_url = "https://example.test/content/CVPR2024/html/Failed_paper.html"
    (tmp_path / "manifest.json").write_text(
        json.dumps([{"url": detail_url, "status": "failed", "error": "old"}]),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2024":
            return httpx.Response(
                200,
                text=f'<a href="{detail_url}">failed</a>',
                request=request,
            )
        return httpx.Response(500, request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2024])

    assert summary.failed_pages == [detail_url]


def test_skipped_events_reflect_current_event_request(tmp_path: Path) -> None:
    responses = [404, 200]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(responses.pop(0), text="", request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        delay=0,
    ) as crawler:
        first_summary = crawler.crawl(["CVPR"], [2024])
        second_summary = crawler.crawl(["CVPR"], [2024])

    assert first_summary.skipped_events == ["CVPR2024"]
    assert second_summary.skipped_events == []


def test_records_and_manifest_are_deterministic_when_details_finish_reversed(
    tmp_path: Path,
) -> None:
    first = "https://example.test/content/CVPR2024/html/First_paper.html"
    second = "https://example.test/content/CVPR2024/html/Second_paper.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2024":
            return httpx.Response(
                200,
                text=f'<a href="{first}">first</a><a href="{second}">second</a>',
                request=request,
            )
        if request.url.path.endswith("First_paper.html"):
            time.sleep(0.02)
        return httpx.Response(
            200,
            text='<div id="papertitle">Title</div>',
            request=request,
        )

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2024])

    assert [record.source_url for record in summary.records] == [first, second]
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert [(entry["url"], entry["status"]) for entry in manifest] == sorted(
        (entry["url"], entry["status"]) for entry in manifest
    )


def test_malformed_manifest_and_cached_html_are_recovered_as_failed_page(
    tmp_path: Path,
) -> None:
    detail_url = "https://example.test/content/CVPR2024/html/Bad_cache_paper.html"
    (tmp_path / "manifest.json").write_text(
        json.dumps(["bad", {"status": "failed"}, {"url": 7, "status": "failed"}]),
        encoding="utf-8",
    )
    cache_path = tmp_path / f"{hashlib.sha256(detail_url.encode()).hexdigest()}.html"
    cache_path.write_bytes(bytes([255, 254]))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=f'<a href="{detail_url}">bad cache</a>',
            request=request,
        )

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2024])

    assert summary.failed_pages == [detail_url]


def test_detail_future_exception_does_not_abort_other_pages(
    tmp_path: Path, monkeypatch
) -> None:
    first = "https://example.test/content/CVPR2024/html/First_paper.html"
    second = "https://example.test/content/CVPR2024/html/Second_paper.html"
    good = CvfRecord(
        title="Good",
        authors=None,
        abstract=None,
        conference="CVPR",
        year=2024,
        source_url=second,
        pdf_url=None,
        keywords=[],
        parser_version="cvf-v1",
        parse_warnings=[],
    )

    with CvfCrawler(tmp_path, delay=0, base_url="https://example.test") as crawler:
        monkeypatch.setattr(
            crawler,
            "_fetch_html",
            lambda url: (
                '<a href="/content/CVPR2024/html/First_paper.html">first</a>'
                '<a href="/content/CVPR2024/html/Second_paper.html">second</a>',
                False,
            ),
        )

        def fetch_and_parse(url: str, conference: str, year: int) -> CvfRecord:
            if url.endswith("First_paper.html"):
                raise ValueError("malformed detail")
            return good

        monkeypatch.setattr(crawler, "_fetch_and_parse", fetch_and_parse)
        summary = crawler.crawl(["CVPR"], [2024])

    assert [record.source_url for record in summary.records] == [second]
    assert summary.failed_pages == [first]

def test_injected_client_receives_descriptive_user_agent(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(404, request=request)

    client = httpx.Client(
        headers={"User-Agent": "test-client"}, transport=httpx.MockTransport(handler)
    )
    crawler = CvfCrawler(tmp_path, client=client, delay=0)
    try:
        crawler.crawl(["CVPR"], [2024])
    finally:
        crawler.close()

    assert requests
    assert requests[0].headers["user-agent"] == "CVInsight/1.0 (CVF metadata crawler)"


def test_resume_controls_reuse_of_successful_cached_detail(tmp_path: Path) -> None:
    detail_url = "https://example.test/content/CVPR2024/html/Test_paper.html"
    detail_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_requests
        if request.url.path == "/CVPR2024":
            return httpx.Response(
                200, text=f'<a href="{detail_url}">test</a>', request=request
            )
        detail_requests += 1
        return httpx.Response(
            200, text='<div id="papertitle">Title</div>', request=request
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with CvfCrawler(tmp_path, base_url="https://example.test", client=client, delay=0) as crawler:
        crawler.crawl(["CVPR"], [2024], resume=False)
        crawler.crawl(["CVPR"], [2024], resume=True)
        crawler.crawl(["CVPR"], [2024], resume=False)

    assert detail_requests == 2