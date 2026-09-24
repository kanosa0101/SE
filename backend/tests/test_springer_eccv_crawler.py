import csv
import importlib.util
import json
from pathlib import Path

from app.crawlers.springer_eccv import (
    CSV_FIELDS,
    abstract_from_inverted_index,
    is_chapter_doi,
    parse_reader_paper,
    parse_volume_links,
    record_to_csv_row,
    records_from_cache,
    fetch_semantic_scholar_abstracts,
    volume_doi_from_url,
)

SCRIPT = Path(__file__).parents[1] / "scripts" / "crawl_springer_eccv.py"
SPEC = importlib.util.spec_from_file_location("crawl_springer_eccv", SCRIPT)
crawl_command = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crawl_command)


def test_parse_volume_links_keeps_only_main_proceedings_for_requested_year():
    page = """
    ## Other volumes
    [Computer Vision – ECCV 2024, Proceedings, Part I](https://link.springer.com/book/10.1007/978-3-031-73232-4)
    [Computer Vision – ECCV 2024, Proceedings, Part II](https://link.springer.com/book/10.1007/978-3-031-73233-1)
    [ECCV 2024 Workshops, Part I](https://link.springer.com/book/10.1007/978-3-031-99999-9)
    [Computer Vision – ECCV 2022, Proceedings, Part I](https://link.springer.com/book/10.1007/978-3-031-19769-7)

    ## Similar content
    [Computer Vision – ECCV 2024](https://link.springer.com/book/10.1007/978-3-031-88888-8)
    """

    assert parse_volume_links(page, 2024) == [
        "https://link.springer.com/book/10.1007/978-3-031-73232-4",
        "https://link.springer.com/book/10.1007/978-3-031-73233-1",
    ]


def test_parse_reader_paper_extracts_title_abstract_and_publisher_keywords():
    page = """Title: A Test for Vision
URL Source: https://link.springer.com/chapter/10.1007/example_1
Published Time: 2024
Markdown Content:
# A Test for Vision

## Abstract
We introduce a robust visual representation.
It improves recognition under challenging conditions.

### Keywords
Computer vision; representation learning; robustness

## References
Not part of the abstract.
"""

    parsed = parse_reader_paper(page)

    assert parsed == {
        "title": "A Test for Vision",
        "abstract": (
            "We introduce a robust visual representation. "
            "It improves recognition under challenging conditions."
        ),
        "keywords": ["Computer vision", "representation learning", "robustness"],
    }


def test_abstract_fallback_reconstructs_openalex_word_order():
    inverted_index = {
        "Vision": [0],
        "models": [2],
        "learn": [1],
        "together.": [3],
    }

    assert abstract_from_inverted_index(inverted_index) == "Vision learn models together."
    assert abstract_from_inverted_index(None) is None


def test_only_individual_springer_chapter_dois_are_accepted():
    assert is_chapter_doi("10.1007/978-3-031-73232-4_17")
    assert not is_chapter_doi("10.1007/978-3-031-73232-4")
    assert not is_chapter_doi("https://link.springer.com/chapter/10.1007/example_17")


def test_springer_book_url_keeps_the_doi_registrant_prefix():
    assert volume_doi_from_url(
        "https://link.springer.com/book/10.1007/978-3-031-73232-4"
    ) == "10.1007/978-3-031-73232-4"


def test_csv_row_uses_existing_paper_schema_and_keeps_abstract():
    record = {
        "title": "A Test for Vision",
        "doi": "10.1007/978-3-031-73232-4_17",
        "authors": ["A. Author", "B. Author"],
        "abstract": "A complete abstract.",
        "keywords": ["computer vision", "robustness"],
        "year": 2024,
        "source_url": "https://link.springer.com/chapter/10.1007/978-3-031-73232-4_17",
        "source": "Springer",
    }

    row = record_to_csv_row(record, crawled_at="2026-09-23T00:00:00Z")

    assert list(row) == CSV_FIELDS
    assert row["abstract"] == "A complete abstract."
    assert row["conference"] == "ECCV"
    assert row["paper_code"] == "10_1007_978_3_031_73232_4_17"


def test_command_writes_expected_csv_schema_including_abstract(tmp_path):
    class FakeCrawler:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def crawl(self, years, limit=None):
            assert years == [2024]
            assert limit == 1
            return [{
                "title": "A Test for Vision",
                "doi": "10.1007/978-3-031-73232-4_17",
                "authors": ["A. Author"],
                "abstract": "A complete abstract.",
                "keywords": ["robustness"],
                "year": 2024,
                "source_url": "https://link.springer.com/chapter/10.1007/978-3-031-73232-4_17",
                "source": "Springer",
            }]

    output = tmp_path / "eccv.csv"
    args = crawl_command._parser().parse_args([
        "--years", "2024", "--limit", "1", "--out", str(output),
        "--cache", str(tmp_path / "cache"),
    ])
    result = crawl_command.run(args, crawler_factory=FakeCrawler)

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert result["records"] == 1
    assert rows[0]["abstract"] == "A complete abstract."
    assert list(rows[0]) == CSV_FIELDS


def test_cache_only_command_exports_cached_records_without_crawling(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    work = {
        "doi": "https://doi.org/10.1007/978-3-031-73232-4_17",
        "title": "OpenAlex title",
        "publication_year": 2024,
        "authorships": [{"author": {"display_name": "A. Author"}}],
        "keywords": [{"display_name": "Computer vision"}],
        "abstract_inverted_index": {"A": [0], "cached": [1], "abstract.": [2]},
    }
    (cache / "openalex.txt").write_text(
        json.dumps({"results": [work]}), encoding="utf-8"
    )
    (cache / "springer.txt").write_text(
        """Title: Publisher title
URL Source: https://link.springer.com/chapter/10.1007/978-3-031-73232-4_17

## Abstract
Publisher abstract.

## Keywords
Visual recognition
""",
        encoding="utf-8",
    )
    output = tmp_path / "partial.csv"

    class NoCrawl:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("cache-only mode must not create a network crawler")

    args = crawl_command._parser().parse_args([
        "--cache-only", "--years", "2024", "--cache", str(cache), "--out", str(output),
    ])
    result = crawl_command.run(args, crawler_factory=NoCrawl)

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert result["records"] == 1
    assert result["missing_abstract"] == 0
    assert rows[0]["title"] == "Publisher title"
    assert rows[0]["abstract"] == "Publisher abstract."
    assert rows[0]["authors"] == "A. Author"
    assert rows[0]["keywords"] == "visual recognition"


def test_fill_missing_mode_fetches_only_rows_without_cached_abstract(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    works = [
        {
            "doi": "https://doi.org/10.1007/978-3-031-73232-4_1",
            "title": "Cached abstract",
            "publication_year": 2024,
            "abstract_inverted_index": {"Already": [0], "available.": [1]},
        },
        {
            "doi": "https://doi.org/10.1007/978-3-031-73232-4_2",
            "title": "Missing abstract",
            "publication_year": 2024,
        },
    ]
    (cache / "openalex.txt").write_text(json.dumps({"results": works}), encoding="utf-8")
    fetched_dois = []
    crawler_options = []

    class FakeCrawler:
        def __init__(self, *_args, **kwargs):
            crawler_options.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def fetch_paper(self, work):
            fetched_dois.append(work["doi"])
            return {**work, "abstract": "Fetched abstract.", "source": "Crossref"}

    output = tmp_path / "filled.csv"
    monkeypatch.setattr(crawl_command, "fetch_semantic_scholar_abstracts", lambda *_args: {})
    args = crawl_command._parser().parse_args([
        "--fill-missing-abstracts", "--springer-fallback", "--years", "2024", "--cache", str(cache),
        "--out", str(output),
    ])

    result = crawl_command.run(args, crawler_factory=FakeCrawler)

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert fetched_dois == ["10.1007/978-3-031-73232-4_2"]
    assert result["abstracts_added"] == 1
    assert result["missing_abstract"] == 0
    assert [row["abstract"] for row in rows] == ["Already available.", "Fetched abstract."]
    assert crawler_options[0]["delay"] == 3.0


def test_fill_missing_mode_defers_rate_limited_fallback_by_default(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    doi = "10.1007/978-3-031-73232-4_1"
    (cache / "openalex.txt").write_text(json.dumps({"results": [{
        "doi": f"https://doi.org/{doi}",
        "title": "Still missing",
        "publication_year": 2024,
    }]}), encoding="utf-8")
    monkeypatch.setattr(crawl_command, "fetch_semantic_scholar_abstracts", lambda *_args: {})

    class NoSlowFallback:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("slow Springer fallback should require explicit opt-in")

    output = tmp_path / "partial.csv"
    args = crawl_command._parser().parse_args([
        "--fill-missing-abstracts", "--years", "2024", "--cache", str(cache),
        "--out", str(output),
    ])
    result = crawl_command.run(args, crawler_factory=NoSlowFallback)

    assert result["missing_abstract"] == 1
    assert result["fallback_attempted"] == 0
    assert result["fallback_deferred"] == 1


def test_fill_missing_mode_uses_batch_abstract_before_slow_fallback(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    doi = "10.1007/978-3-031-73232-4_1"
    (cache / "openalex.txt").write_text(json.dumps({"results": [{
        "doi": f"https://doi.org/{doi}",
        "title": "Missing abstract",
        "publication_year": 2024,
    }]}), encoding="utf-8")
    output = tmp_path / "filled.csv"
    seen_dois = []

    def batch_lookup(dois, _cache):
        seen_dois.extend(dois)
        return {doi.casefold(): "Fast batch abstract."}

    monkeypatch.setattr(crawl_command, "fetch_semantic_scholar_abstracts", batch_lookup)

    class NoFallback:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("batch hits must not trigger slower per-paper requests")

    args = crawl_command._parser().parse_args([
        "--fill-missing-abstracts", "--years", "2024", "--cache", str(cache),
        "--out", str(output),
    ])
    result = crawl_command.run(args, crawler_factory=NoFallback)

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert seen_dois == [doi]
    assert result["abstracts_added"] == 1
    assert result["abstracts_attempted"] == 1
    assert result["missing_abstract"] == 0
    assert rows[0]["source"] == "Semantic Scholar"
    assert rows[0]["abstract"] == "Fast batch abstract."


def test_fill_missing_mode_can_skip_batch_api_and_run_slow_fallback(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    doi = "10.1007/978-3-031-73232-4_1"
    (cache / "openalex.txt").write_text(json.dumps({"results": [{
        "doi": f"https://doi.org/{doi}",
        "title": "Missing abstract",
        "publication_year": 2024,
    }]}), encoding="utf-8")

    def fail_if_batch_is_called(*_args):
        raise AssertionError("skip mode must not call the Semantic Scholar API")

    monkeypatch.setattr(crawl_command, "fetch_semantic_scholar_abstracts", fail_if_batch_is_called)
    fetched_dois = []

    class FakeCrawler:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def fetch_paper(self, record):
            fetched_dois.append(record["doi"])
            return {**record, "abstract": "Fallback abstract.", "source": "Springer"}

    output = tmp_path / "filled.csv"
    args = crawl_command._parser().parse_args([
        "--fill-missing-abstracts", "--springer-fallback", "--skip-semantic-scholar",
        "--years", "2024", "--cache", str(cache), "--out", str(output),
    ])

    result = crawl_command.run(args, crawler_factory=FakeCrawler)

    assert fetched_dois == [doi]
    assert result["fallback_attempted"] == 1
    assert result["missing_abstract"] == 0


def test_fill_missing_mode_resumes_from_csv_without_scanning_full_cache(tmp_path, monkeypatch):
    input_csv = tmp_path / "existing.csv"
    rows = [{
        "title": "Missing abstract",
        "paper_code": "10_1007_978_3_031_73232_4_1",
        "abstract": "",
        "authors": "A. Author",
        "conference": "ECCV",
        "year": 2024,
        "source": "Springer",
        "source_url": "https://link.springer.com/chapter/10.1007/978-3-031-73232-4_1",
        "keywords": "vision",
        "crawled_at": "2026-09-24T00:00:00Z",
        "parser_version": "springer-eccv-v1",
    }, {
        "title": "Existing abstract",
        "paper_code": "10_1007_978_3_030_01234_2_1",
        "abstract": "Already available.",
        "authors": "B. Author",
        "conference": "ECCV",
        "year": 2018,
        "source": "Springer",
        "source_url": "https://link.springer.com/chapter/10.1007/978-3-030-01234-2_1",
        "keywords": "vision",
        "crawled_at": "2026-09-24T00:00:00Z",
        "parser_version": "springer-eccv-v1",
    }]
    with input_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    def fail_if_full_cache_is_scanned(*_args):
        raise AssertionError("CSV resume mode must not scan all cached response files")

    monkeypatch.setattr(crawl_command, "records_from_cache", fail_if_full_cache_is_scanned)
    monkeypatch.setattr(crawl_command, "fetch_semantic_scholar_abstracts", fail_if_full_cache_is_scanned)

    class FakeCrawler:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def fetch_paper(self, record):
            return {**record, "abstract": "Recovered abstract.", "source": "Springer"}

    args = crawl_command._parser().parse_args([
        "--fill-missing-abstracts", "--springer-fallback", "--skip-semantic-scholar",
        "--resume-csv", str(input_csv), "--years", "2024", "--out", str(input_csv),
    ])

    result = crawl_command.run(args, crawler_factory=FakeCrawler)

    with input_csv.open(encoding="utf-8-sig", newline="") as handle:
        updated = list(csv.DictReader(handle))
    assert result["records"] == 2
    assert result["abstracts_attempted"] == 1
    assert updated[0]["abstract"] == "Recovered abstract."
    assert updated[1]["abstract"] == "Already available."


def test_semantic_scholar_batch_lookup_uses_doi_ids_and_reuses_cache(tmp_path):
    doi = "10.1007/978-3-031-73232-4_17"
    missing_doi = "10.1007/978-3-031-73232-4_18"

    class FakeResponse:
        status_code = 200
        headers = {}
        text = json.dumps([{
            "externalIds": {"DOI": doi},
            "abstract": "A batch-retrieved abstract.",
        }, {
            "externalIds": {"DOI": missing_doi},
            "abstract": None,
        }])

        def raise_for_status(self):
            pass

    class FakeClient:
        calls = []

        def post(self, url, *, params, json):
            self.calls.append((url, params, json))
            return FakeResponse()

    client = FakeClient()
    found = fetch_semantic_scholar_abstracts([doi, missing_doi], tmp_path, client=client)
    reused = fetch_semantic_scholar_abstracts([missing_doi], tmp_path, client=client)

    assert found == {doi.casefold(): "A batch-retrieved abstract."}
    assert reused == found
    assert len(client.calls) == 1
    assert client.calls[0][2] == {"ids": [f"DOI:{doi}", f"DOI:{missing_doi}"]}


def test_cache_records_include_semantic_scholar_abstract_fallback(tmp_path):
    doi = "10.1007/978-3-031-73232-4_17"
    (tmp_path / "openalex.txt").write_text(json.dumps({"results": [{
        "doi": f"https://doi.org/{doi}",
        "title": "A chapter",
        "publication_year": 2024,
    }]}), encoding="utf-8")
    s2_cache = tmp_path / "semantic_scholar"
    s2_cache.mkdir()
    (s2_cache / "cached.json").write_text(json.dumps([{
        "externalIds": {"DOI": doi},
        "abstract": "A cached batch abstract.",
    }]), encoding="utf-8")

    records = records_from_cache(tmp_path, [2024])

    assert records[0]["abstract"] == "A cached batch abstract."
    assert records[0]["source"] == "Semantic Scholar"
