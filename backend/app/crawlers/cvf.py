"""Deterministic parsing and cache-aware crawling for CVF Open Access pages."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


PARSER_VERSION = "cvf-v1"
DEFAULT_BASE_URL = "https://openaccess.thecvf.com"
USER_AGENT = "CVInsight/1.0 (CVF metadata crawler)"


@dataclass(frozen=True)
class CvfRecord:
    title: str
    authors: str | None
    abstract: str | None
    conference: str
    year: int
    source_url: str
    pdf_url: str | None
    keywords: list[str]
    parser_version: str
    parse_warnings: list[str]


@dataclass(frozen=True)
class CrawlSummary:
    records: list[CvfRecord] = field(default_factory=list)
    failed_pages: list[str] = field(default_factory=list)
    skipped_events: list[str] = field(default_factory=list)
    manifest_path: Path | None = None


def _text(node: object) -> str:
    if node is None:
        return ""
    return " ".join(str(node.get_text(" ", strip=True)).split())  # type: ignore[union-attr]


def parse_index(html: str, base_url: str) -> list[str]:
    """Return unique paper-detail URLs from a CVF event index."""

    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="/content/"]'):
        href = link.get("href")
        if not href or not href.lower().split("?", 1)[0].endswith("_paper.html"):
            continue
        resolved = urljoin(base_url.rstrip("/") + "/", href)
        if resolved not in seen:
            seen.add(resolved)
            urls.append(resolved)
    return urls


def parse_detail(html: str, conference: str, year: int, source_url: str) -> CvfRecord:
    """Parse one CVF paper page without performing I/O."""

    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one("#papertitle"))
    authors = _text(soup.select_one("#authors")) or None
    abstract = _text(soup.select_one("#abstract")) or None
    pdf_url: str | None = None
    for link in soup.select('a[href]'):
        href = link.get("href")
        if href and href.lower().split("?", 1)[0].endswith(".pdf"):
            pdf_url = urljoin(source_url, href)
            break

    warnings: list[str] = []
    if abstract is None:
        warnings.append("missing_abstract")
    if not title:
        warnings.append("missing_title")

    return CvfRecord(
        title=title,
        authors=authors,
        abstract=abstract,
        conference=conference,
        year=year,
        source_url=source_url,
        pdf_url=pdf_url,
        keywords=[],
        parser_version=PARSER_VERSION,
        parse_warnings=warnings,
    )


class _RateLimiter:
    def __init__(self, delay: float, sleeper: Callable[[float], None]) -> None:
        self.delay = max(0.0, delay)
        self.sleeper = sleeper
        self.lock = threading.Lock()
        self.next_request = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            wait_for = max(0.0, self.next_request - now)
            self.next_request = max(now, self.next_request) + self.delay
        if wait_for:
            self.sleeper(wait_for)


class CvfCrawler:
    """Fetch CVF event pages while keeping requests cacheable and bounded."""

    def __init__(
        self,
        cache_dir: Path,
        delay: float = 0.25,
        workers: int = 4,
        timeout: float = 20.0,
        max_retries: int = 3,
        *,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.workers = max(1, workers)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True
        )
        self._owns_client = client is None
        self._limiter = _RateLimiter(delay, sleeper)
        self._manifest_path = self.cache_dir / "manifest.json"
        self._manifest_lock = threading.Lock()
        self._manifest = self._load_manifest()
        self._current_failed_urls: set[str] = set()

    def _load_manifest(self) -> list[dict[str, str]]:
        if not self._manifest_path.exists():
            return []
        try:
            data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        manifest: list[dict[str, str]] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            url = entry.get("url")
            status = entry.get("status")
            if not isinstance(url, str) or not isinstance(status, str):
                continue
            clean_entry = {"url": url, "status": status}
            if isinstance(entry.get("error"), str):
                clean_entry["error"] = entry["error"]
            manifest.append(clean_entry)
        return manifest

    def _record_manifest(self, url: str, status: str, error: str | None = None) -> None:
        entry = {"url": url, "status": status}
        if error:
            entry["error"] = error
        with self._manifest_lock:
            self._manifest.append(entry)
            self._manifest.sort(
                key=lambda item: (
                    item["url"],
                    item["status"],
                    item.get("error", ""),
                )
            )
            if status == "failed":
                self._current_failed_urls.add(url)
            self._manifest_path.write_text(
                json.dumps(self._manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"

    def _fetch_html(self, url: str) -> tuple[str | None, bool]:
        cache_path = self._cache_path(url)
        if cache_path.exists():
            try:
                html = cache_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                self._record_manifest(url, "failed", str(exc))
                return None, False
            self._record_manifest(url, "cached")
            return html, False

        last_error = "request failed"
        for attempt in range(self.max_retries + 1):
            try:
                self._limiter.wait()
                response = self.client.get(url)
                if response.status_code == 404:
                    self._record_manifest(url, "not_found")
                    return None, True
                response.raise_for_status()
                html = response.text
                cache_path.write_text(html, encoding="utf-8")
                self._record_manifest(url, "fetched")
                return html, False
            except (httpx.HTTPError, OSError, UnicodeError) as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    self._limiter.sleeper(2**attempt * 0.25)
        self._record_manifest(url, "failed", last_error)
        return None, False

    def crawl_event(self, conference: str, year: int) -> list[CvfRecord]:
        event_url = f"{self.base_url}/{conference}{year}"
        index_html, skipped = self._fetch_html(event_url)
        if skipped or index_html is None:
            return []
        detail_urls = parse_index(index_html, self.base_url)
        records: list[CvfRecord] = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                url: executor.submit(self._fetch_and_parse, url, conference, year)
                for url in detail_urls
            }
            for url in detail_urls:
                try:
                    record = futures[url].result()
                except Exception as exc:
                    self._record_manifest(url, "failed", str(exc))
                    continue
                if record is not None:
                    records.append(record)
        return records

    def _fetch_and_parse(
        self, url: str, conference: str, year: int
    ) -> CvfRecord | None:
        html, _ = self._fetch_html(url)
        return parse_detail(html, conference, year, url) if html is not None else None

    def crawl(
        self,
        conferences: list[str],
        years: list[int],
        limit: int | None = None,
        resume: bool = False,
    ) -> CrawlSummary:
        del resume
        self._current_failed_urls = set()
        records: list[CvfRecord] = []
        skipped_events: list[str] = []
        for conference in conferences:
            for year in years:
                event = f"{conference}{year}"
                event_records = self.crawl_event(conference, year)
                if not event_records and self._event_was_not_found(event):
                    skipped_events.append(event)
                records.extend(event_records)
                if limit is not None and len(records) >= limit:
                    return CrawlSummary(
                        records=records[:limit],
                        failed_pages=sorted(self._current_failed_urls),
                        skipped_events=skipped_events,
                        manifest_path=self._manifest_path,
                    )
        return CrawlSummary(
            records=records,
            failed_pages=sorted(self._current_failed_urls),
            skipped_events=skipped_events,
            manifest_path=self._manifest_path,
        )

    def _failed_urls(self) -> set[str]:
        return {
            entry["url"]
            for entry in self._manifest
            if entry.get("status") == "failed"
        }

    def _event_was_not_found(self, event: str) -> bool:
        return any(
            entry.get("url", "").rstrip("/").endswith("/" + event)
            and entry.get("status") == "not_found"
            for entry in self._manifest
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "CvfCrawler":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


__all__ = ["CrawlSummary", "CvfCrawler", "CvfRecord", "parse_detail", "parse_index"]