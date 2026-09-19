import hashlib
import json
import threading
import time
from pathlib import Path

import httpx

from app.crawlers.cvf import CvfCrawler, CvfRecord, _RateLimiter, parse_detail, parse_index


FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_index_deduplicates_and_resolves_relative_links() -> None:
    urls = parse_index(read_fixture("cvf_index.html"), "https://openaccess.thecvf.com")

    assert urls == [
        "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html",
        "https://openaccess.thecvf.com/content/CVPR2024/html/Another_Test_Paper_CVPR_2024_paper.html",
    ]


LEGACY_INDEX_HTML = """
<html><body>
  <a href="content_cvpr_2016/html/Legacy_Paper_One_CVPR_2016_paper.html">Paper One</a>
  <a href="content_cvpr_2016/html/Legacy_Paper_Two_CVPR_2016_paper.html">Paper Two</a>
  <a href="content_cvpr_2016/html/Legacy_Paper_Two_CVPR_2016_paper.html">Paper Two duplicate</a>
  <a href="/menu">Menu</a>
</body></html>
"""


def test_parse_index_supports_legacy_relative_content_links() -> None:
    urls = parse_index(LEGACY_INDEX_HTML, "https://openaccess.thecvf.com")

    assert urls == [
        "https://openaccess.thecvf.com/content_cvpr_2016/html/Legacy_Paper_One_CVPR_2016_paper.html",
        "https://openaccess.thecvf.com/content_cvpr_2016/html/Legacy_Paper_Two_CVPR_2016_paper.html",
    ]


DYNAMIC_INDEX_HTML = """
<html><body>
  <a href="CVPR2019.py?day=2019-06-18">Tuesday</a>
  <a href="CVPR2019.py?day=2019-06-19">Wednesday</a>
  <a href="CVPR2019.py?day=all">All days</a>
  <a href="http://cvpr2019.thecvf.com">Site</a>
</body></html>
"""


def test_parse_day_urls_lists_per_day_pages_without_all_view() -> None:
    from app.crawlers.cvf import parse_day_urls

    urls = parse_day_urls(DYNAMIC_INDEX_HTML, "https://openaccess.thecvf.com/CVPR2019")

    assert urls == [
        "https://openaccess.thecvf.com/CVPR2019.py?day=2019-06-18",
        "https://openaccess.thecvf.com/CVPR2019.py?day=2019-06-19",
    ]


def test_parse_all_papers_url_accepts_dynamic_page_variant() -> None:
    from app.crawlers.cvf import parse_all_papers_url

    html = '<a href="CVPR2019.py?day=all">All papers</a>'
    assert parse_all_papers_url(html, "https://openaccess.thecvf.com/CVPR2019") == (
        "https://openaccess.thecvf.com/CVPR2019.py?day=all"
    )


def test_parse_detail_extracts_cvf_metadata() -> None:
    detail_url = "https://openaccess.thecvf.com/content/CVPR2024/html/A_Test_Paper_CVPR_2024_paper.html"

    record = parse_detail(read_fixture("cvf_detail.html"), "CVPR", 2024, detail_url)

    assert record.title == "A Test Paper"
    assert record.authors == "Alice Example and Bob Example"
    assert record.conference == "CVPR"
    assert record.year == 2024
    assert record.abstract == "A concise abstract."
    assert record.keywords == ["diffusion model", "vision-language model"]
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


def test_invalid_utf8_cache_is_recovered_as_failed_page(tmp_path: Path) -> None:
    detail_url = "https://example.test/content/CVPR2024/html/Invalid_cache_paper.html"
    cache_path = tmp_path / f"{hashlib.sha256(detail_url.encode()).hexdigest()}.html"
    cache_path.write_text("not a CVF page", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2024":
            return httpx.Response(200, text=f'<a href="{detail_url}">invalid</a>', request=request)
        return httpx.Response(500, request=request)

    with CvfCrawler(tmp_path, base_url="https://example.test",
                    client=httpx.Client(transport=httpx.MockTransport(handler)),
                    max_retries=0, delay=0) as crawler:
        summary = crawler.crawl(["CVPR"], [2024])

    assert summary.failed_pages == [detail_url]


def test_manifest_snapshot_is_safe_while_workers_record_entries(tmp_path: Path) -> None:
    crawler = CvfCrawler(tmp_path, delay=0)
    errors: list[Exception] = []

    def record(index: int) -> None:
        try:
            crawler._record_manifest(f"https://example.test/{index}", "fetched")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=record, args=(index,)) for index in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    crawler.close()

    assert errors == []
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 24
    assert [entry["url"] for entry in manifest] == sorted(entry["url"] for entry in manifest)


def test_retry_backoff_is_recorded_without_real_sleep(tmp_path: Path) -> None:
    responses = [500, 500, 200]
    sleeps: list[float] = []
    detail_url = "https://example.test/content/CVPR2024/html/Retry_paper.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2024":
            return httpx.Response(200, text=f'<a href="{detail_url}">retry</a>', request=request)
        return httpx.Response(responses.pop(0), text='<div id="papertitle">Title</div>', request=request)

    with CvfCrawler(tmp_path, base_url="https://example.test",
                    client=httpx.Client(transport=httpx.MockTransport(handler)),
                    max_retries=2, delay=0, sleeper=sleeps.append) as crawler:
        summary = crawler.crawl(["CVPR"], [2024])

    assert len(summary.records) == 1
    assert sleeps == [0.25, 0.5]


def test_rate_limiter_releases_lock_before_sleep() -> None:
    entered = threading.Event()
    release = threading.Event()
    sleeps: list[float] = []

    def sleeper(delay: float) -> None:
        sleeps.append(delay)
        entered.set()
        release.wait(timeout=1)

    limiter = _RateLimiter(1, sleeper)
    limiter.next_request = time.monotonic() + 1
    first = threading.Thread(target=limiter.wait)
    first.start()
    assert entered.wait(timeout=1)
    second = threading.Thread(target=limiter.wait)
    second.start()
    second.join(timeout=1)
    release.set()
    first.join(timeout=1)

    assert not second.is_alive()
    assert len(sleeps) == 2


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
        headers={"User-Agent": "test-client", "X-Caller": "kept"},
        transport=httpx.MockTransport(handler),
    )
    crawler = CvfCrawler(tmp_path, client=client, delay=0)
    crawler.crawl(["CVPR"], [2024])
    crawler.close()

    assert requests
    assert requests[0].headers["user-agent"] == "CVInsight/1.0 (CVF metadata crawler)"
    assert requests[0].headers["x-caller"] == "kept"
    assert client.is_closed is False


def test_internal_client_is_closed_by_crawler(tmp_path: Path) -> None:
    crawler = CvfCrawler(tmp_path, delay=0)
    client = crawler.client
    crawler.close()

    assert client.is_closed is True


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
def test_crawl_follows_all_papers_view_from_event_landing_page(tmp_path: Path) -> None:
    detail_url = "https://example.test/content/CVPR2025/html/A_Test_Paper_CVPR_2025_paper.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2025" and request.url.params.get("day") is None:
            return httpx.Response(
                200,
                text='<a href="/CVPR2025?day=all">All Papers</a>',
                request=request,
            )
        if request.url.path == "/CVPR2025" and request.url.params.get("day") == "all":
            return httpx.Response(200, text=f'<a href="{detail_url}">paper</a>', request=request)
        if request.url.path.endswith("_paper.html"):
            return httpx.Response(200, text=read_fixture("cvf_detail.html"), request=request)
        return httpx.Response(404, request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2025])

    assert len(summary.records) == 1
    assert summary.records[0].source_url == detail_url
def test_crawl_limit_bounds_detail_requests(tmp_path: Path) -> None:
    detail_urls = [
        f"https://example.test/content/CVPR2025/html/Paper_{index}_paper.html"
        for index in range(5)
    ]
    requested_details: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2025" and request.url.params.get("day") is None:
            return httpx.Response(200, text='<a href="/CVPR2025?day=all">All Papers</a>', request=request)
        if request.url.path == "/CVPR2025" and request.url.params.get("day") == "all":
            links = "".join(f'<a href="{url}">paper</a>' for url in detail_urls)
            return httpx.Response(200, text=links, request=request)
        if request.url.path.endswith("_paper.html"):
            requested_details.append(str(request.url))
            return httpx.Response(200, text=read_fixture("cvf_detail.html"), request=request)
        return httpx.Response(404, request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2025], limit=2)

    assert len(summary.records) == 2
    assert len(requested_details) == 2
def test_detail_404_is_reported_in_failed_pages(tmp_path: Path) -> None:
    detail_url = "https://example.test/content/CVPR2025/html/Missing_paper.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2025":
            return httpx.Response(200, text=f'<a href="{detail_url}">paper</a>', request=request)
        return httpx.Response(404, request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2025])

    assert summary.records == []
    assert summary.failed_pages == [detail_url]
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert any(item["url"] == detail_url and item["status"] == "not_found" for item in manifest)


def test_all_papers_view_is_merged_with_landing_links(tmp_path: Path) -> None:
    first_url = "https://example.test/content/CVPR2025/html/First_paper.html"
    second_url = "https://example.test/content/CVPR2025/html/Second_paper.html"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/CVPR2025" and request.url.params.get("day") is None:
            return httpx.Response(
                200,
                text=f'<a href="{first_url}">first</a><a href="/CVPR2025?day=all">all</a>',
                request=request,
            )
        if request.url.path == "/CVPR2025" and request.url.params.get("day") == "all":
            return httpx.Response(200, text=f'<a href="{second_url}">second</a>', request=request)
        if request.url.path.endswith("_paper.html"):
            return httpx.Response(200, text=read_fixture("cvf_detail.html"), request=request)
        return httpx.Response(404, request=request)

    with CvfCrawler(
        tmp_path,
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        delay=0,
    ) as crawler:
        summary = crawler.crawl(["CVPR"], [2025])

    assert {record.source_url for record in summary.records} == {first_url, second_url}


def test_manifest_updates_from_two_crawler_instances_are_merged(tmp_path: Path) -> None:
    first_url = "https://example.test/content/CVPR2025/html/First_paper.html"
    second_url = "https://example.test/content/CVPR2025/html/Second_paper.html"
    first = CvfCrawler(tmp_path, client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))))
    second = CvfCrawler(tmp_path, client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, request=request))))

    try:
        first._record_manifest(first_url, "fetched")
        second._record_manifest(second_url, "fetched")
    finally:
        first.close()
        second.close()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert {item["url"] for item in manifest} == {first_url, second_url}
