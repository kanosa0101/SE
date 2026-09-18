import csv
import importlib.util
import json
from pathlib import Path

from app.crawlers.cvf import CrawlSummary, CvfRecord

SCRIPT = Path(__file__).parents[1] / "scripts" / "crawl_cvf.py"
SPEC = importlib.util.spec_from_file_location("crawl_cvf", SCRIPT)
assert SPEC and SPEC.loader
crawl_cvf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crawl_cvf)


class FakeCrawler:
    detail_fetches = 0
    event_fetches = 0

    def __init__(self, cache_dir, **kwargs):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.cache_dir / "manifest.json"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def crawl(self, conferences, years, limit=None, resume=False):
        pages = []
        records = []
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            manifest = []
        for venue in conferences:
            for year in years:
                event = f"{venue}{year}"
                url = f"https://openaccess.thecvf.com/{event}"
                if event == "ICCV2023":
                    manifest.append({"url": url, "status": "not_found", "error": "HTTP 404"})
                    continue
                FakeCrawler.event_fetches += 1
                manifest.append({"url": url, "status": "fetched"})
                detail_url = f"https://openaccess.thecvf.com/content/{event}/html/Example_paper.html"
                if detail_url not in pages:
                    if not resume or not self._cached(detail_url):
                        FakeCrawler.detail_fetches += 1
                    pages.append(detail_url)
                    manifest.append({"url": detail_url, "status": "cached" if resume else "fetched"})
                records.append(CvfRecord(
                    title="An example paper", authors="A. Author", abstract=None,
                    conference=venue, year=year, source_url=detail_url, pdf_url=None,
                    keywords=["  Vision ", "vision", "Learning"], parser_version="cvf-v1",
                    parse_warnings=["missing_abstract"],
                ))
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return CrawlSummary(records=records[:limit] if limit is not None else records,
                            skipped_events=["ICCV2023"], manifest_path=self.manifest_path,
                            discovered_pages=pages)

    def _cached(self, url):
        return any(entry.get("url") == url and entry.get("status") in {"fetched", "cached"}
                   for entry in json.loads(self.manifest_path.read_text(encoding="utf-8")))


def test_command_writes_schema_manifest_and_resumes_cached_details(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(crawl_cvf, "CvfCrawler", FakeCrawler)
    output = tmp_path / "cvf.csv"
    cache = tmp_path / "cache"
    crawl_cvf.main(["--out", str(output), "--cache", str(cache)])
    crawl_cvf.main(["--out", str(output), "--cache", str(cache), "--resume"])
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == crawl_cvf.CSV_FIELDS
    assert rows[0]["source"] == "CVF"
    assert rows[0]["abstract"] == ""
    assert rows[0]["keywords"] == "learning; vision"
    assert rows[0]["paper_code"] == "example"
    assert rows[0]["crawled_at"]
    assert FakeCrawler.detail_fetches == 7
    manifest = json.loads(output.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["events"]) == 8
    skipped = next(item for item in manifest["events"] if item["event"] == "ICCV2023")
    assert skipped["status"] == "skipped"
    assert "404" in skipped["reason"]
    assert manifest["pages"]
    assert "records_parsed=" in capsys.readouterr().out


def test_event_candidates_are_exact_and_dry_run_does_not_write_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl_cvf, "CvfCrawler", FakeCrawler)
    assert crawl_cvf.EVENT_CANDIDATES == [
        ("CVPR", 2022), ("CVPR", 2023), ("CVPR", 2024), ("CVPR", 2025),
        ("ICCV", 2023), ("ICCV", 2025), ("ECCV", 2022), ("ECCV", 2024),
    ]
    output = tmp_path / "dry.csv"
    crawl_cvf.main(["--out", str(output), "--cache", str(tmp_path / "cache"), "--dry-run"])
    assert not output.exists()
    assert not output.with_suffix(".manifest.json").exists()

class DuplicateCrawler(FakeCrawler):
    def crawl(self, conferences, years, limit=None, resume=False):
        record = CvfRecord(
            title="A paper", authors="A. Author", abstract="Abstract",
            conference=conferences[0], year=years[0],
            source_url="https://openaccess.thecvf.com/content/CVPR2022/html/A_paper.html",
            pdf_url=None, keywords=[], parser_version="cvf-v1", parse_warnings=[],
        )
        return CrawlSummary(records=[record, record], failed_pages=[])


def test_records_parsed_counts_records_before_deduplication(tmp_path):
    output = tmp_path / "duplicates.csv"
    result = crawl_cvf.run(
        crawl_cvf._parser().parse_args(["--venues", "CVPR", "--years", "2022", "--out", str(output), "--cache", str(tmp_path / "cache")]),
        crawler_factory=DuplicateCrawler,
    )

    assert result["records_parsed"] == 2
    assert result["duplicates"] == 1
    assert len(list(csv.DictReader(output.open(encoding="utf-8", newline="")))) == 1


class RecoveryCrawler(FakeCrawler):
    def crawl(self, conferences, years, limit=None, resume=False):
        event = f"{conferences[0]}{years[0]}"
        url = f"https://openaccess.thecvf.com/{event}"
        manifest = [
            {"url": url, "status": "failed", "error": "old failure", "recorded_at": "2026-09-18T00:00:00Z"},
            {"url": url, "status": "not_found", "recorded_at": "2026-09-18T00:01:00Z"},
            {"url": url, "status": "fetched", "recorded_at": "2026-09-18T00:02:00Z"},
        ]
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return CrawlSummary(records=[], failed_pages=[], skipped_events=[])


def test_event_status_uses_newer_success_after_older_failure(tmp_path):
    output = tmp_path / "recovery.csv"
    crawl_cvf.run(
        crawl_cvf._parser().parse_args(
            ["--venues", "CVPR", "--years", "2022", "--out", str(output), "--cache", str(tmp_path / "cache")]
        ),
        crawler_factory=RecoveryCrawler,
    )

    manifest = json.loads(output.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert manifest["events"] == [{"event": "CVPR2022", "url": "https://openaccess.thecvf.com/CVPR2022", "status": "complete"}]


def test_current_summary_does_not_include_historical_detail_pages(tmp_path, monkeypatch):
    class CurrentRunCrawler(FakeCrawler):
        def crawl(self, conferences, years, limit=None, resume=False):
            self.manifest_path.write_text(json.dumps([
                {"url": "https://openaccess.thecvf.com/content/OLD/html/Old_paper.html", "status": "fetched"},
                {"url": "https://openaccess.thecvf.com/content/CVPR2022/html/New_paper.html", "status": "fetched"},
            ]), encoding="utf-8")
            return CrawlSummary(records=[], failed_pages=[], skipped_events=[],
                                manifest_path=self.manifest_path,
                                discovered_pages=["https://openaccess.thecvf.com/content/CVPR2022/html/New_paper.html"])

    output = tmp_path / "scoped.csv"
    result = crawl_cvf.run(
        crawl_cvf._parser().parse_args(["--venues", "CVPR", "--years", "2022",
                                        "--out", str(output), "--cache", str(tmp_path / "cache")]),
        crawler_factory=CurrentRunCrawler,
    )

    assert result["detail_discovered"] == 1
    manifest = json.loads(output.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert [entry["url"] for entry in manifest["pages"]] == [
        "https://openaccess.thecvf.com/content/CVPR2022/html/New_paper.html"
    ]


def test_parser_exposes_timeout_and_retry_options():
    args = crawl_cvf._parser().parse_args(["--timeout", "7.5", "--max-retries", "5"])

    assert args.timeout == 7.5
    assert args.max_retries == 5


def test_run_passes_timeout_and_retries_to_crawler(tmp_path):
    captured = {}

    class ConfigCrawler(FakeCrawler):
        def __init__(self, cache_dir, **kwargs):
            captured.update(kwargs)
            super().__init__(cache_dir, **kwargs)

    crawl_cvf.run(
        crawl_cvf._parser().parse_args(["--venues", "CVPR", "--years", "2022", "--timeout", "7.5",
                                        "--max-retries", "5", "--out", str(tmp_path / "out.csv"),
                                        "--cache", str(tmp_path / "cache")]),
        crawler_factory=ConfigCrawler,
    )

    assert captured["timeout"] == 7.5
    assert captured["max_retries"] == 5
