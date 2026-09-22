"""Deterministic parsing and cache-aware crawling for CVF Open Access pages."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urljoin, urlparse

if os.name == "nt":
    import msvcrt
else:
    import fcntl

import httpx
from bs4 import BeautifulSoup

from app.services.keywords import normalize_keyword


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
    discovered_pages: list[str] = field(default_factory=list)


def _text(node: object) -> str:
    if node is None:
        return ""
    return " ".join(str(node.get_text(" ", strip=True)).split())  # type: ignore[union-attr]


def _normalized_title(text: str) -> str:
    return "".join(char for char in text.casefold() if char.isalnum())


def _title_matches(query: str, candidate: str) -> bool:
    normalized_query = _normalized_title(query)
    normalized_candidate = _normalized_title(candidate)
    if not normalized_query or not normalized_candidate:
        return False
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return True
    query_tokens = set(re.findall(r"[a-z0-9]+", query.casefold()))
    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate.casefold()))
    return bool(query_tokens) and len(query_tokens & candidate_tokens) / len(query_tokens) >= 0.6


def parse_index_entries(html: str, base_url: str) -> list[tuple[str, str]]:
    """Return unique detail URLs and their visible titles from a CVF index."""

    soup = BeautifulSoup(html, "html.parser")
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    # 老年份（2016-2020）主页的论文链接是相对路径 content_cvpr_2016/...，
    # 新年份 day=all 页是绝对路径 /content/CVPR2021/...，两种形式都要命中，
    # 最终由 _paper.html 后缀检查兜底防止误匹配。
    for link in soup.select('a[href*="content"]'):
        href = link.get("href")
        if not href or not href.lower().split("?", 1)[0].endswith("_paper.html"):
            continue
        resolved = urljoin(base_url.rstrip("/") + "/", href)
        if resolved not in seen:
            seen.add(resolved)
            entries.append((resolved, _text(link)))
    return entries


def parse_index(html: str, base_url: str) -> list[str]:
    """Return unique paper-detail URLs from a CVF event index."""

    return [url for url, _ in parse_index_entries(html, base_url)]


def parse_all_papers_url(html: str, event_url: str) -> str | None:
    """Return the event's explicit all-papers view when the landing page has one."""

    event_path = urlparse(event_url).path.rstrip("/")
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.select("a[href]"):
        href = link.get("href")
        if not href:
            continue
        resolved = urljoin(event_url, href)
        parsed = urlparse(resolved)
        # 2019-2020 的动态页把 day 链接挂在 CVPR2019.py 上，接受这一变体。
        if parsed.path.rstrip("/") in (event_path, f"{event_path}.py") and parse_qs(parsed.query).get("day") == ["all"]:
            return resolved
    return None


def parse_day_urls(html: str, event_url: str) -> list[str]:
    """Return per-day listing URLs for events that publish no all-papers view."""

    event_path = urlparse(event_url).path.rstrip("/")
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        resolved = urljoin(event_url, link.get("href") or "")
        parsed = urlparse(resolved)
        if parsed.path.rstrip("/") not in (event_path, f"{event_path}.py"):
            continue
        day_values = parse_qs(parsed.query).get("day")
        if not day_values or day_values == ["all"]:
            continue
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

    raw_keywords: list[str] = []
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").casefold()
        if name in {"keywords", "citation_keywords"}:
            content = meta.get("content")
            if content:
                raw_keywords.append(str(content))
    for node in soup.select("#keywords, .keywords"):
        value = _text(node)
        if value:
            raw_keywords.append(re.sub(r"^keywords?\s*:\s*", "", value, flags=re.IGNORECASE))
    keywords = sorted({normalized for value in raw_keywords for item in re.split(r"[;,|]", value)
                       if (normalized := normalize_keyword(item))})

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
        keywords=keywords,
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
        self._resume = False
        self._limiter = _RateLimiter(delay, sleeper)
        self._manifest_path = self.cache_dir / "manifest.json"
        self._manifest_lock = threading.Lock()
        self._manifest = self._load_manifest()
        self._current_failed_urls: set[str] = set()
        self._current_event: str | None = None
        self._current_event_was_not_found = False
        self._current_discovered_pages: set[str] = set()

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
            if isinstance(entry.get("recorded_at"), str):
                clean_entry["recorded_at"] = entry["recorded_at"]
            manifest.append(clean_entry)
        return manifest

    def _write_atomic(self, path: Path, content: str) -> None:
        fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    @contextmanager
    def _manifest_process_lock(self):
        lock_path = self._manifest_path.with_suffix(".lock")
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _manifest_snapshot(self) -> list[dict[str, str]]:
        with self._manifest_lock:
            return [entry.copy() for entry in self._manifest]

    def _record_manifest(self, url: str, status: str, error: str | None = None) -> None:
        entry = {
            "url": url,
            "status": status,
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        }
        if error:
            entry["error"] = error
        with self._manifest_lock:
            with self._manifest_process_lock():
                self._manifest = self._load_manifest()
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
                self._write_atomic(
                    self._manifest_path,
                    json.dumps(self._manifest, ensure_ascii=False, indent=2),
                )

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"

    def _is_valid_cached_html(self, url: str, html: str) -> bool:
        if not html.strip():
            return False
        soup = BeautifulSoup(html, "html.parser")
        if soup.find() is None:
            return False
        if "/content/" in url:
            return bool(
                soup.select_one("#papertitle, #authors, #abstract")
                or soup.select_one('a[href$=".pdf"]')
            )
        return bool(soup.select('a[href*="/content/"]') or soup.body)

    def _fetch_html(self, url: str) -> tuple[str | None, bool]:
        cache_path = self._cache_path(url)
        successful_cached = {
            entry["url"]
            for entry in self._manifest_snapshot()
            if entry.get("status") in {"fetched", "cached"}
        }
        if cache_path.exists() and (self._resume or url not in successful_cached):
            try:
                html = cache_path.read_text(encoding="utf-8")
                if not self._is_valid_cached_html(url, html):
                    raise ValueError("invalid cached HTML")
            except (OSError, UnicodeError, ValueError) as exc:
                self._record_manifest(url, "failed", str(exc))
                return None, False
            self._record_manifest(url, "cached")
            return html, False

        last_error = "request failed"
        for attempt in range(self.max_retries + 1):
            try:
                self._limiter.wait()
                response = self.client.get(url, headers={"User-Agent": USER_AGENT})
                if response.status_code == 404:
                    self._record_manifest(url, "not_found")
                    return None, True
                response.raise_for_status()
                html = response.text
                self._write_atomic(cache_path, html)
                self._record_manifest(url, "fetched")
                return html, False
            except (httpx.HTTPError, OSError, UnicodeError) as exc:
                last_error = str(exc)
                if attempt < self.max_retries:
                    self._limiter.sleeper(2**attempt * 0.25)
        self._record_manifest(url, "failed", last_error)
        return None, False

    def find_title(
        self,
        title: str,
        conferences: list[str],
        years: list[int],
    ) -> CvfRecord | None:
        """Find one title by scanning CVF indexes before fetching its detail page."""

        self._resume = True
        for conference in conferences:
            for year in years:
                event_url = f"{self.base_url}/{conference}{year}"
                index_html, skipped = self._fetch_html(event_url)
                if skipped or index_html is None:
                    continue

                index_pages = [event_url]
                all_papers_url = parse_all_papers_url(index_html, event_url)
                if all_papers_url:
                    index_pages.append(all_papers_url)
                else:
                    index_pages.extend(parse_day_urls(index_html, event_url))

                entries: list[tuple[str, str]] = []
                seen_urls: set[str] = set()
                for index_page in dict.fromkeys(index_pages):
                    page_html = index_html if index_page == event_url else self._fetch_html(index_page)[0]
                    if page_html is None:
                        continue
                    for detail_url, link_title in parse_index_entries(page_html, self.base_url):
                        if detail_url in seen_urls:
                            continue
                        seen_urls.add(detail_url)
                        entries.append((detail_url, link_title))

                for detail_url, link_title in entries:
                    if not _title_matches(title, link_title):
                        continue
                    detail_html, not_found = self._fetch_html(detail_url)
                    if not_found or detail_html is None:
                        continue
                    record = parse_detail(detail_html, conference, year, detail_url)
                    if _title_matches(title, record.title):
                        return record
        return None

    def crawl_event(
        self, conference: str, year: int, limit: int | None = None
    ) -> list[CvfRecord]:
        event = f"{conference}{year}"
        self._current_event = event
        event_url = f"{self.base_url}/{event}"
        index_html, skipped = self._fetch_html(event_url)
        self._current_event_was_not_found = skipped
        if skipped or index_html is None:
            return []
        detail_urls = parse_index(index_html, self.base_url)
        all_papers_url = parse_all_papers_url(index_html, event_url)
        if all_papers_url:
            all_index_html, all_skipped = self._fetch_html(all_papers_url)
            if not all_skipped and all_index_html is not None:
                detail_urls = list(dict.fromkeys(
                    [*detail_urls, *parse_index(all_index_html, self.base_url)]
                ))
        # 无论是否有 day=all 汇总页都合并分日列表页，保证不漏掉汇总页缺失的论文。
        for day_url in parse_day_urls(index_html, event_url):
            day_html, day_skipped = self._fetch_html(day_url)
            if day_skipped or day_html is None:
                self._current_discovered_pages.add(day_url)
                continue
            self._current_discovered_pages.add(day_url)
            detail_urls.extend(parse_index(day_html, self.base_url))
        detail_urls = list(dict.fromkeys(detail_urls))
        if limit is not None:
            detail_urls = detail_urls[:limit]
        self._current_discovered_pages.update(detail_urls)
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
        html, not_found = self._fetch_html(url)
        if not_found:
            with self._manifest_lock:
                self._current_failed_urls.add(url)
        return parse_detail(html, conference, year, url) if html is not None else None

    def crawl(
        self,
        conferences: list[str],
        years: list[int],
        limit: int | None = None,
        resume: bool = False,
    ) -> CrawlSummary:
        self._resume = resume
        self._current_failed_urls = set()
        self._current_discovered_pages = set()
        records: list[CvfRecord] = []
        skipped_events: list[str] = []
        for conference in conferences:
            for year in years:
                event = f"{conference}{year}"
                remaining = None if limit is None else max(limit - len(records), 0)
                event_records = self.crawl_event(conference, year, limit=remaining)
                if not event_records and self._event_was_not_found(event):
                    skipped_events.append(event)
                records.extend(event_records)
                if limit is not None and len(records) >= limit:
                    return CrawlSummary(
                        records=records[:limit],
                        failed_pages=sorted(self._current_failed_urls),
                        skipped_events=skipped_events,
                        manifest_path=self._manifest_path,
                        discovered_pages=sorted(self._current_discovered_pages),
                    )
        return CrawlSummary(
            records=records,
            failed_pages=sorted(self._current_failed_urls),
            skipped_events=skipped_events,
            manifest_path=self._manifest_path,
            discovered_pages=sorted(self._current_discovered_pages),
        )

    def _failed_urls(self) -> set[str]:
        return {
            entry["url"]
            for entry in self._manifest_snapshot()
            if entry.get("status") == "failed"
        }

    def _event_was_not_found(self, event: str) -> bool:
        return self._current_event == event and self._current_event_was_not_found

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "CvfCrawler":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


__all__ = ["CrawlSummary", "CvfCrawler", "CvfRecord", "parse_all_papers_url", "parse_detail", "parse_index"]
