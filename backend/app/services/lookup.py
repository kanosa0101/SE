import re
from pathlib import Path
from typing import Any

import httpx

from app.crawlers.cvf import CvfCrawler
from app.config import Settings
from app.schemas import PaperCreate


class LookupUnavailableError(RuntimeError):
    pass


# OpenAlex 等来源使用会议全称或带缩写的全称，而本系统口径只接受 CVPR、ICCV、ECCV。
_CONFERENCE_ALIASES = {
    "CVPR": ("CVPR", "COMPUTER VISION AND PATTERN RECOGNITION"),
    "ICCV": ("ICCV", "INTERNATIONAL CONFERENCE ON COMPUTER VISION"),
    "ECCV": ("ECCV", "EUROPEAN CONFERENCE ON COMPUTER VISION"),
}


def _venue_text(record: dict[str, Any]) -> str:
    parts = [record.get("conference"), record.get("venue")]
    for key in ("primary_location", "host_venue"):
        container = record.get(key)
        if isinstance(container, dict):
            source = container.get("source")
            if isinstance(source, dict):
                parts.append(source.get("display_name"))
            parts.append(container.get("display_name"))
    return " ".join(str(value) for value in parts if value).upper()


def _conference_from_record(record: dict[str, Any]) -> str | None:
    text = _venue_text(record)
    for conference, aliases in _CONFERENCE_ALIASES.items():
        if any(alias in text for alias in aliases):
            return conference
    return None


def _normalized_title(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def _title_matches(query: str, candidate: str) -> bool:
    normalized_query = _normalized_title(query)
    normalized_candidate = _normalized_title(candidate)
    if not normalized_query or not normalized_candidate:
        return False
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return True
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    candidate_tokens = set(re.findall(r"[a-z0-9]+", candidate.lower()))
    if not query_tokens:
        return False
    return len(query_tokens & candidate_tokens) / len(query_tokens) >= 0.6


def _to_paper_create(record: dict[str, Any], conference: str) -> PaperCreate:
    authorships = record.get("authorships", [])
    authors = ", ".join(
        item.get("author", {}).get("display_name", "")
        for item in authorships
        if isinstance(item, dict) and item.get("author", {}).get("display_name")
    )
    primary_location = record.get("primary_location")
    source_url = (
        primary_location.get("landing_page_url")
        if isinstance(primary_location, dict)
        else None
    )
    return PaperCreate(
        title=record["title"],
        abstract=record.get("abstract") or None,
        authors=authors or None,
        conference=conference,
        year=int(record.get("publication_year") or 0),
        source="online",
        source_url=source_url,
        keywords=[item.get("display_name", "") for item in record.get("keywords", []) if isinstance(item, dict)],
    )


def lookup_title(title: str, settings: Settings) -> PaperCreate:
    if not settings.lookup_url:
        raise LookupUnavailableError("未配置在线检索源")
    try:
        response = httpx.get(settings.lookup_url, params={"search": title, "per-page": 25}, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LookupUnavailableError("在线检索源暂时不可用") from exc
    records = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        raise LookupUnavailableError("在线检索没有返回匹配论文")
    valid_records = [record for record in records if isinstance(record, dict) and record.get("title")]
    for record in valid_records:
        if not _title_matches(title, str(record["title"])):
            continue
        conference = _conference_from_record(record)
        if conference is not None:
            return _to_paper_create(record, conference)
    if any(_conference_from_record(record) for record in valid_records):
        raise LookupUnavailableError("在线检索结果与给定标题不够匹配")
    raise LookupUnavailableError("在线检索结果不属于 CVPR、ICCV 或 ECCV")


def lookup_cvf_title(title: str, settings: Settings) -> PaperCreate:
    with CvfCrawler(
        Path(settings.cvf_cache_dir),
        base_url=settings.cvf_base_url,
        delay=0.1,
        workers=4,
        timeout=10.0,
        max_retries=1,
    ) as crawler:
        record = crawler.find_title(
            title,
            ["CVPR", "ICCV", "ECCV"],
            list(range(2025, 2015, -1)),
        )
    if record is None:
        raise LookupUnavailableError("CVF 网站中没有找到匹配论文")
    return PaperCreate(
        title=record.title,
        abstract=record.abstract,
        authors=record.authors,
        conference=record.conference,
        year=record.year,
        source="CVF",
        source_url=record.source_url,
        parser_version=record.parser_version,
        keywords=record.keywords,
    )
