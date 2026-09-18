from typing import Any

import httpx

from app.config import Settings
from app.schemas import PaperCreate


class LookupUnavailableError(RuntimeError):
    pass


def _conference_from_record(record: dict[str, Any]) -> str | None:
    text = " ".join(
        str(value)
        for value in (
            record.get("conference"),
            record.get("venue"),
            record.get("host_venue", {}).get("display_name") if isinstance(record.get("host_venue"), dict) else None,
        )
        if value
    ).upper()
    for conference in ("CVPR", "ICCV", "ECCV"):
        if conference in text:
            return conference
    return None


def lookup_title(title: str, settings: Settings) -> PaperCreate:
    if not settings.lookup_url:
        raise LookupUnavailableError("未配置在线检索源")
    try:
        response = httpx.get(settings.lookup_url, params={"search": title, "per-page": 5}, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise LookupUnavailableError("在线检索源暂时不可用") from exc
    records = payload.get("results", []) if isinstance(payload, dict) else []
    record = next((item for item in records if isinstance(item, dict) and item.get("title")), None)
    if record is None:
        raise LookupUnavailableError("在线检索没有返回匹配论文")
    conference = _conference_from_record(record)
    if conference is None:
        raise LookupUnavailableError("检索结果不属于 CVPR、ICCV 或 ECCV")
    authorships = record.get("authorships", [])
    authors = ", ".join(
        item.get("author", {}).get("display_name", "")
        for item in authorships
        if isinstance(item, dict) and item.get("author", {}).get("display_name")
    )
    return PaperCreate(
        title=record["title"],
        abstract=record.get("abstract") or None,
        authors=authors or None,
        conference=conference,
        year=int(record.get("publication_year") or 0),
        source="online",
        source_url=record.get("primary_location", {}).get("landing_page_url")
        if isinstance(record.get("primary_location"), dict)
        else None,
        keywords=[item.get("display_name", "") for item in record.get("keywords", []) if isinstance(item, dict)],
    )
