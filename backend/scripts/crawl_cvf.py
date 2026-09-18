"""Command-line crawl orchestration for CVF Open Access metadata."""
from __future__ import annotations
import argparse, csv, json, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.crawlers.cvf import PARSER_VERSION, CrawlSummary, CvfCrawler, CvfRecord

EVENT_CANDIDATES = [("CVPR", 2022), ("CVPR", 2023), ("CVPR", 2024), ("CVPR", 2025),
                    ("ICCV", 2023), ("ICCV", 2025), ("ECCV", 2022), ("ECCV", 2024)]
CSV_FIELDS = ["title", "paper_code", "abstract", "authors", "conference", "year", "source",
              "source_url", "keywords", "crawled_at", "parser_version"]

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venues", nargs="+", default=["CVPR", "ICCV", "ECCV"])
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    parser.add_argument("--out", type=Path, default=Path("../data/cvf_2022_2025.csv"))
    parser.add_argument("--cache", type=Path, default=Path("../data/raw/cvf"))
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser

def _paper_code(source_url: str) -> str:
    stem = re.sub(r"_paper$", "", Path(urlparse(source_url).path).stem, flags=re.I)
    return re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()

def _keywords(values: list[str]) -> str:
    unique = {}
    for value in values:
        clean = " ".join(value.split())
        if clean: unique.setdefault(clean.casefold(), clean)
    return "; ".join(unique[key] for key in sorted(unique))

def _atomic_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)

def _read_cache_manifest(path: Path) -> list[dict[str, str]]:
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError): return []
    return [entry for entry in data if isinstance(entry, dict) and isinstance(entry.get("url"), str)] if isinstance(data, list) else []

def _event_entry(event, cache_manifest, skipped):
    venue, year = event; name = f"{venue}{year}"; url = f"https://openaccess.thecvf.com/{name}"
    matches = [entry for entry in cache_manifest if entry.get("url") == url]
    latest = matches[-1] if matches else {}
    if name in skipped or latest.get("status") == "not_found":
        return {"event": name, "url": url, "status": "skipped", "reason": latest.get("error", "HTTP 404")}
    if latest.get("status") == "failed":
        return {"event": name, "url": url, "status": "failed", "reason": latest.get("error", "HTTP request failed")}
    return {"event": name, "url": url, "status": "complete"}

def run(args: argparse.Namespace, crawler_factory=None) -> dict[str, object]:
    crawler_factory = crawler_factory or CvfCrawler
    selected = [(venue, year) for venue, year in EVENT_CANDIDATES if venue in args.venues and year in args.years]
    records: list[CvfRecord] = []; skipped: set[str] = set()
    with crawler_factory(args.cache, delay=args.delay, workers=args.workers) as crawler:
        for venue, year in selected:
            remaining = None if args.limit is None else max(args.limit - len(records), 0)
            summary: CrawlSummary = crawler.crawl([venue], [year], limit=remaining, resume=args.resume)
            records.extend(summary.records)
            if args.limit is not None: records = records[:args.limit]
            skipped.update(summary.skipped_events)
    by_url = {}; duplicates = 0
    for record in records:
        if record.source_url in by_url: duplicates += 1
        else: by_url[record.source_url] = record
    records = list(by_url.values()); cache_manifest = _read_cache_manifest(args.cache / "manifest.json")
    pages = [entry for entry in cache_manifest if "/content/" in entry.get("url", "")]
    detail_urls = {entry["url"] for entry in pages}; failed_pages = {entry["url"] for entry in pages if entry.get("status") == "failed"}
    crawled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [{"title": r.title, "paper_code": _paper_code(r.source_url), "abstract": r.abstract or "", "authors": r.authors or "",
             "conference": r.conference, "year": r.year, "source": "CVF", "source_url": r.source_url,
             "keywords": _keywords(r.keywords), "crawled_at": crawled_at, "parser_version": r.parser_version or PARSER_VERSION} for r in records]
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest = {"parser_version": PARSER_VERSION, "events": [_event_entry(event, cache_manifest, skipped) for event in selected], "pages": pages}
    if not args.dry_run:
        _atomic_csv(args.out, rows); manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"events_seen": len(selected), "event_skipped": sum(item["status"] == "skipped" for item in manifest["events"]),
              "detail_discovered": len(detail_urls), "records_parsed": len(records), "duplicates": duplicates,
              "parse_errors": len(failed_pages), "missing_abstract": sum(r.abstract is None for r in records),
              "csv": str(args.out), "manifest": str(manifest_path)}
    print("\n".join(f"{key}={value}" for key, value in result.items())); return result

def main(argv: list[str] | None = None) -> int:
    run(_parser().parse_args(argv)); return 0

if __name__ == "__main__": raise SystemExit(main())
