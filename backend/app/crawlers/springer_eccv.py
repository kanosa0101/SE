"""Crawl ECCV proceedings metadata and abstracts from Springer chapters."""

from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.services.keywords import normalize_keyword


PARSER_VERSION = "springer-eccv-v1"
CSV_FIELDS = [
    "title", "paper_code", "abstract", "authors", "conference", "year",
    "source", "source_url", "keywords", "crawled_at", "parser_version",
]
SEED_BOOKS = {
    2016: "https://link.springer.com/book/10.1007/978-3-319-46448-0",
    2018: "https://link.springer.com/book/10.1007/978-3-030-01246-5",
    2020: "https://link.springer.com/book/10.1007/978-3-030-58452-8",
    2022: "https://link.springer.com/book/10.1007/978-3-031-19769-7",
    2024: "https://link.springer.com/book/10.1007/978-3-031-73232-4",
}
OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"
READER_URL = "https://r.jina.ai/"


def parse_volume_links(markdown: str, year: int) -> list[str]:
    """Find Springer main-proceedings volumes, excluding ECCV workshops."""
    section = re.search(
        r"(?ims)^[ \t]*##[ \t]+Other volumes[ \t]*\r?\n(.*?)(?=^[ \t]*##[ \t]+|\Z)",
        markdown,
    )
    source = section.group(1) if section else markdown
    pattern = re.compile(r"\[([^\]]+)\]\((https?://link\.springer\.com/book/[^)\s]+)\)", re.I)
    urls: list[str] = []
    seen: set[str] = set()
    for title, url in pattern.findall(source):
        if not re.search(rf"\bECCV\s*{year}\b", title, re.I):
            continue
        if "workshop" in title.casefold():
            continue
        clean_url = url.split("?", 1)[0].rstrip(".,")
        if clean_url not in seen:
            seen.add(clean_url)
            urls.append(clean_url)
    return urls


def _markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ims)^#{{1,6}}\s*{re.escape(heading)}\s*\n(.*?)(?=^#{{1,6}}\s+|\Z)"
    )
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def _plain_text(markdown: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"[`*_]", "", text)
    return " ".join(html.unescape(text).split()).strip()


def parse_reader_paper(markdown: str) -> dict[str, Any]:
    """Parse title, abstract, and keywords from a Jina Reader Springer page."""
    title_match = re.search(r"(?im)^Title:\s*(.+?)\s*$", markdown)
    if title_match is None:
        title_match = re.search(r"(?m)^#\s+(.+?)\s*$", markdown)
    title = _plain_text(title_match.group(1)) if title_match else ""
    abstract = _plain_text(_markdown_section(markdown, "Abstract")) or None
    keyword_text = _markdown_section(markdown, "Keywords")
    keywords = [
        value for value in (_plain_text(item) for item in re.split(r"[;,|\n]", keyword_text))
        if value
    ]
    return {"title": title, "abstract": abstract, "keywords": keywords}


def abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str | None:
    """Restore OpenAlex's position-indexed abstract representation, if present."""
    if not index:
        return None
    words: list[str | None] = [None] * (max(position for positions in index.values() for position in positions) + 1)
    for word, positions in index.items():
        for position in positions:
            if 0 <= position < len(words):
                words[position] = word
    abstract = " ".join(word for word in words if word)
    return abstract or None


def is_chapter_doi(doi: str | None) -> bool:
    return bool(doi and re.fullmatch(r"10\.\d{4,9}/\S+_\d+", doi.strip(), re.I))


def volume_doi_from_url(volume_url: str) -> str:
    match = re.search(r"/book/(10\.\d{4,9}/[^/?#]+)", urlparse(volume_url).path, re.I)
    if not match:
        raise ValueError(f"not a Springer book URL: {volume_url}")
    return match.group(1)


def record_to_csv_row(record: dict[str, Any], crawled_at: str) -> dict[str, Any]:
    doi = str(record["doi"])
    paper_code = re.sub(r"[^A-Za-z0-9]+", "_", doi).strip("_").lower()
    raw_keywords = record.get("keywords") or []
    keywords = sorted({
        normalized for value in raw_keywords
        if (normalized := normalize_keyword(str(value)))
    })
    return {
        "title": record.get("title") or "",
        "paper_code": paper_code,
        "abstract": record.get("abstract") or "",
        "authors": "; ".join(record.get("authors") or []),
        "conference": "ECCV",
        "year": record.get("year"),
        "source": record.get("source") or "Springer",
        "source_url": record.get("source_url") or f"https://link.springer.com/chapter/{doi}",
        "keywords": "; ".join(keywords),
        "crawled_at": crawled_at,
        "parser_version": PARSER_VERSION,
    }


def _reader_url(url: str) -> str:
    return f"{READER_URL}{url}"


def _paper_url(doi: str) -> str:
    return f"https://link.springer.com/chapter/{doi}"


def _clean_crossref_abstract(value: str | None) -> str | None:
    if not value:
        return None
    from bs4 import BeautifulSoup

    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return " ".join(text.split()) or None


def fetch_semantic_scholar_abstracts(
    dois: list[str], cache_dir: Path, client: httpx.Client | None = None,
) -> dict[str, str]:
    """Fetch abstracts for DOI batches of at most 500 and cache each response."""
    owned_client = client is None
    client = client or httpx.Client(timeout=45.0, follow_redirects=True)
    cache_dir = Path(cache_dir) / "semantic_scholar"
    found: dict[str, str] = {}
    cached_dois: set[str] = set()
    unique_dois = list(dict.fromkeys(doi for doi in dois if doi))
    try:
        for path in cache_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, list):
                for paper in payload:
                    if not isinstance(paper, dict):
                        continue
                    doi = (paper.get("externalIds") or {}).get("DOI")
                    abstract = paper.get("abstract")
                    if doi:
                        key = str(doi).casefold()
                        cached_dois.add(key)
                        if abstract and str(abstract).strip():
                            found[key] = str(abstract).strip()

        pending = [doi for doi in unique_dois if doi.casefold() not in cached_dois]
        for start in range(0, len(pending), 500):
            batch = pending[start:start + 500]
            if start:
                time.sleep(2.0)
            cache_key = hashlib.sha256("\n".join(batch).encode("utf-8")).hexdigest()
            cache_path = cache_dir / f"{cache_key}.json"
            for attempt in range(3):
                try:
                    response = client.post(
                        "https://api.semanticscholar.org/graph/v1/paper/batch",
                        params={"fields": "externalIds,abstract"},
                        json={"ids": [f"DOI:{doi}" for doi in batch]},
                    )
                    if response.status_code == 429 and attempt < 2:
                        retry_after = response.headers.get("Retry-After")
                        try:
                            wait = max(2.0, float(retry_after)) if retry_after else 2 ** (attempt + 1)
                        except ValueError:
                            wait = 2 ** (attempt + 1)
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as error:
                    if error.response.status_code != 429 or attempt == 2:
                        raise
            else:
                raise RuntimeError("Semantic Scholar batch request did not complete")

            content = response.text
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(content, encoding="utf-8")
            payload = json.loads(content)
            if not isinstance(payload, list):
                continue
            for paper in payload:
                if not isinstance(paper, dict):
                    continue
                doi = (paper.get("externalIds") or {}).get("DOI")
                abstract = paper.get("abstract")
                if doi:
                    key = str(doi).casefold()
                    cached_dois.add(key)
                    if abstract and str(abstract).strip():
                        found[key] = str(abstract).strip()
    finally:
        if owned_client:
            client.close()
    return found


def records_from_cache(cache_dir: Path, years: list[int]) -> list[dict[str, Any]]:
    """Assemble available chapter records from cached responses without network access."""
    works: dict[str, dict[str, Any]] = {}
    publisher_pages: dict[str, dict[str, Any]] = {}
    crossref_abstracts: dict[str, str] = {}
    semantic_scholar_abstracts: dict[str, str] = {}
    chapter_url = re.compile(
        r"(?im)^URL Source:\s*https?://link\.springer\.com/chapter/"
        r"(10\.\d{4,9}/[^\s?#]+)"
    )

    for path in Path(cache_dir).glob("*.txt"):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict) and isinstance(payload.get("results"), list):
            for item in payload["results"]:
                doi = (item.get("doi") or "").removeprefix("https://doi.org/")
                year = item.get("publication_year")
                if not is_chapter_doi(doi) or year not in years:
                    continue
                authors = [
                    authorship.get("author", {}).get("display_name", "")
                    for authorship in item.get("authorships", [])
                    if authorship.get("author", {}).get("display_name")
                ]
                keywords = [
                    keyword.get("display_name", "")
                    for keyword in item.get("keywords", [])
                    if keyword.get("display_name")
                ]
                works[doi.casefold()] = {
                    "doi": doi,
                    "title": item.get("title") or "",
                    "year": year,
                    "authors": authors,
                    "keywords": keywords,
                    "abstract_inverted_index": item.get("abstract_inverted_index"),
                    "source_url": _paper_url(doi),
                }
            continue

        if isinstance(payload, dict) and isinstance(payload.get("message"), dict):
            message = payload["message"]
            doi = message.get("DOI") or ""
            abstract = _clean_crossref_abstract(message.get("abstract"))
            if is_chapter_doi(doi) and abstract:
                crossref_abstracts[doi.casefold()] = abstract
            continue

        match = chapter_url.search(content)
        if match and is_chapter_doi(match.group(1)):
            publisher_pages[match.group(1).casefold()] = parse_reader_paper(content)

    for path in (Path(cache_dir) / "semantic_scholar").glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for paper in payload:
            if not isinstance(paper, dict):
                continue
            doi = (paper.get("externalIds") or {}).get("DOI")
            abstract = paper.get("abstract")
            if doi and abstract:
                semantic_scholar_abstracts[str(doi).casefold()] = str(abstract).strip()

    records = []
    for key in sorted(works):
        work = works[key]
        publisher = publisher_pages.get(key, {})
        abstract = publisher.get("abstract") or abstract_from_inverted_index(
            work.get("abstract_inverted_index")
        )
        source = "Springer" if publisher.get("abstract") else "OpenAlex"
        if not abstract and key in crossref_abstracts:
            abstract = crossref_abstracts[key]
            source = "Crossref"
        if not abstract and key in semantic_scholar_abstracts:
            abstract = semantic_scholar_abstracts[key]
            source = "Semantic Scholar"
        records.append({
            **work,
            "title": publisher.get("title") or work["title"],
            "abstract": abstract,
            "keywords": publisher.get("keywords") or work["keywords"],
            "source": source,
        })
    return records


class SpringerEccvCrawler:
    """Discover ECCV chapters from OpenAlex and cache Springer page responses."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        delay: float = 0.2,
        workers: int = 4,
        client: httpx.Client | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = max(0.0, delay)
        self.workers = max(1, workers)
        self.client = client or httpx.Client(
            timeout=timeout,
            follow_redirects=True,
        )
        self._owns_client = client is None
        self._request_lock = threading.Lock()
        self._next_request_at = 0.0

    def __enter__(self) -> "SpringerEccvCrawler":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self.client.close()

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.txt"

    def _get_text(self, url: str) -> str:
        cache_path = self._cache_path(url)
        if cache_path.is_file():
            return cache_path.read_text(encoding="utf-8")

        for attempt in range(self.max_retries + 1):
            with self._request_lock:
                pause = max(0.0, self._next_request_at - time.monotonic())
                self._next_request_at = max(time.monotonic(), self._next_request_at) + self.delay
            if pause:
                time.sleep(pause)
            try:
                headers = (
                    {"X-Target-Selector": "main", "X-Return-Format": "markdown"}
                    if url.startswith(READER_URL) else None
                )
                response = self.client.get(url, headers=headers)
                response.raise_for_status()
                content = response.text
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(content, encoding="utf-8")
                return content
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in {429, 500, 502, 503, 504} or attempt == self.max_retries:
                    raise
            except httpx.RequestError:
                if attempt == self.max_retries:
                    raise
            time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"request did not complete: {url}")

    def discover_volumes(self, year: int) -> list[str]:
        seed = SEED_BOOKS[year]
        page = self._get_text(_reader_url(seed))
        volumes = parse_volume_links(page, year)
        if seed not in volumes:
            volumes.insert(0, seed)
        return volumes

    def discover_chapters(self, volume_url: str, year: int) -> list[dict[str, Any]]:
        volume_doi = volume_doi_from_url(volume_url)
        cursor = "*"
        chapters: dict[str, dict[str, Any]] = {}
        while cursor:
            params = {
                "filter": f"doi_starts_with:{volume_doi}",
                "per-page": 200,
                "cursor": cursor,
                "select": "doi,title,publication_year,authorships,keywords,abstract_inverted_index",
            }
            request = self.client.build_request("GET", OPENALEX_URL, params=params)
            payload = json.loads(self._get_text(str(request.url)))
            for work in payload.get("results", []):
                doi = (work.get("doi") or "").removeprefix("https://doi.org/")
                if not is_chapter_doi(doi) or work.get("publication_year") != year:
                    continue
                authors = [
                    authorship.get("author", {}).get("display_name", "")
                    for authorship in work.get("authorships", [])
                    if authorship.get("author", {}).get("display_name")
                ]
                keywords = [
                    item.get("display_name", "") for item in work.get("keywords", [])
                    if item.get("display_name")
                ]
                chapters[doi.casefold()] = {
                    "doi": doi,
                    "title": work.get("title") or "",
                    "year": year,
                    "authors": authors,
                    "keywords": keywords,
                    "abstract_inverted_index": work.get("abstract_inverted_index"),
                    "source_url": _paper_url(doi),
                }
            cursor = payload.get("meta", {}).get("next_cursor")
        return [chapters[key] for key in sorted(chapters)]

    def fetch_paper(self, work: dict[str, Any]) -> dict[str, Any]:
        """Fetch one chapter's publisher abstract, with metadata-source fallbacks."""
        doi = work["doi"]
        parsed: dict[str, Any] = {}
        try:
            parsed = parse_reader_paper(self._get_text(_reader_url(_paper_url(doi))))
        except (httpx.HTTPError, OSError):
            pass

        abstract = parsed.get("abstract") or abstract_from_inverted_index(
            work.get("abstract_inverted_index")
        )
        source = "Springer" if parsed.get("abstract") else "OpenAlex"
        if not abstract:
            try:
                crossref_url = f"{CROSSREF_URL}/{quote(doi, safe='')}"
                message = json.loads(self._get_text(crossref_url)).get("message", {})
                abstract = _clean_crossref_abstract(message.get("abstract"))
                if abstract:
                    source = "Crossref"
            except (httpx.HTTPError, ValueError):
                pass

        publisher_keywords = parsed.get("keywords") or []
        return {
            **work,
            "title": parsed.get("title") or work.get("title") or "",
            "abstract": abstract,
            "authors": work.get("authors") or [],
            "keywords": publisher_keywords or work.get("keywords") or [],
            "source": source,
            "source_url": _paper_url(doi),
        }

    def crawl(self, years: list[int], limit: int | None = None) -> list[dict[str, Any]]:
        chapters: dict[str, dict[str, Any]] = {}
        for year in years:
            if year not in SEED_BOOKS:
                raise ValueError(f"unsupported ECCV year: {year}")
            for volume_url in self.discover_volumes(year):
                for work in self.discover_chapters(volume_url, year):
                    chapters[work["doi"].casefold()] = work

        works = [chapters[key] for key in sorted(chapters)]
        if limit is not None:
            works = works[:limit]
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            return list(executor.map(self.fetch_paper, works))
