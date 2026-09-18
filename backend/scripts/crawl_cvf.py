"""Command-line crawl orchestration for CVF Open Access metadata."""
from __future__ import annotations
import argparse, csv, io, json, math, os, re, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.crawlers.cvf import PARSER_VERSION, CrawlSummary, CvfCrawler, CvfRecord
from app.services.keywords import normalize_keyword

EVENT_CANDIDATES = [("CVPR", 2022), ("CVPR", 2023), ("CVPR", 2024), ("CVPR", 2025),
                    ("ICCV", 2023), ("ICCV", 2025), ("ECCV", 2022), ("ECCV", 2024)]
CSV_FIELDS = ["title", "paper_code", "abstract", "authors", "conference", "year", "source",
              "source_url", "keywords", "crawled_at", "parser_version"]

def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venues", nargs="+", default=["CVPR", "ICCV", "ECCV"])
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    parser.add_argument("--out", type=Path, default=Path("../data/cvf_2022_2025.csv"))
    parser.add_argument("--cache", type=Path, default=Path("../data/raw/cvf"))
    parser.add_argument("--delay", type=_non_negative_float, default=0.25)
    parser.add_argument("--workers", type=_positive_int, default=4)
    parser.add_argument("--timeout", type=_positive_float, default=20.0)
    parser.add_argument("--max-retries", type=_non_negative_int, default=3)
    parser.add_argument("--limit", type=_positive_int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser

def _paper_code(source_url: str) -> str:
    stem = re.sub(r"_paper$", "", Path(urlparse(source_url).path).stem, flags=re.I)
    return re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()

def _keywords(values: list[str]) -> str:
    normalized = {normalize_keyword(value) for value in values}
    return "; ".join(sorted(value for value in normalized if value))

def _stage_temp(path: Path, content: bytes) -> Path:
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return temporary_path
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_publish_pair(csv_path: Path, csv_content: str,
                          manifest_path: Path, manifest_content: str) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        staged.extend([
            _stage_temp(csv_path, csv_content.encode("utf-8")),
            _stage_temp(manifest_path, manifest_content.encode("utf-8")),
        ])
        for path in (csv_path, manifest_path):
            if path.exists():
                backups[path] = _stage_temp(path, path.read_bytes())
        os.replace(staged[0], csv_path)
        published.append(csv_path)
        os.replace(staged[1], manifest_path)
        published.append(manifest_path)
        _fsync_directory(csv_path.parent)
    except BaseException:
        try:
            for path in reversed(published):
                backup = backups.get(path)
                if backup is not None:
                    os.replace(backup, path)
                    backups.pop(path, None)
                else:
                    path.unlink(missing_ok=True)
            for backup in backups.values():
                backup.unlink(missing_ok=True)
        except BaseException as rollback_error:
            raise RuntimeError("output publication failed and rollback failed") from rollback_error
        raise
    finally:
        for path in staged:
            path.unlink(missing_ok=True)
        for path in backups.values():
            path.unlink(missing_ok=True)


def _csv_content(rows: list[dict[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()

def _read_cache_manifest(path: Path) -> list[dict[str, str]]:
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError): return []
    return [entry for entry in data if isinstance(entry, dict) and isinstance(entry.get("url"), str)] if isinstance(data, list) else []

def _event_entry(event, cache_manifest, skipped, limited):
    venue, year = event; name = f"{venue}{year}"; url = f"https://openaccess.thecvf.com/{name}"
    if name in limited:
        return {"event": name, "url": url, "status": "skipped", "reason": "limit reached"}
    matches = [entry for entry in cache_manifest if entry.get("url") == url]
    timestamped = [entry for entry in matches if entry.get("recorded_at")]
    latest = max(timestamped, key=lambda entry: entry["recorded_at"]) if timestamped else (matches[-1] if matches else {})
    if name in skipped or latest.get("status") == "not_found":
        return {"event": name, "url": url, "status": "skipped", "reason": latest.get("error", "HTTP 404")}
    if latest.get("status") == "failed":
        return {"event": name, "url": url, "status": "failed", "reason": latest.get("error", "HTTP request failed")}
    return {"event": name, "url": url, "status": "complete"}

def run(args: argparse.Namespace, crawler_factory=None) -> dict[str, object]:
    crawler_factory = crawler_factory or CvfCrawler
    selected = [(venue, year) for venue, year in EVENT_CANDIDATES if venue in args.venues and year in args.years]
    records: list[CvfRecord] = []; skipped: set[str] = set(); limited: set[str] = set(); failed_pages: set[str] = set(); discovered_pages: set[str] = set()
    with crawler_factory(args.cache, delay=args.delay, workers=args.workers,
                         timeout=args.timeout, max_retries=args.max_retries) as crawler:
        for venue, year in selected:
            remaining = None if args.limit is None else max(args.limit - len(records), 0)
            summary: CrawlSummary = crawler.crawl([venue], [year], limit=remaining, resume=args.resume)
            records.extend(summary.records)
            if args.limit is not None: records = records[:args.limit]
            failed_pages.update(summary.failed_pages)
            skipped.update(summary.skipped_events)
            discovered_pages.update(summary.discovered_pages)
            if args.limit is not None and len(records) >= args.limit:
                limited.update(f"{v}{y}" for v, y in selected[selected.index((venue, year)) + 1:])
                break
    if failed_pages and not records:
        raise RuntimeError(f"crawl failed for {len(failed_pages)} page(s); refusing to publish outputs")
    records_parsed = len(records)
    by_url = {}; duplicates = 0
    for record in records:
        if record.source_url in by_url: duplicates += 1
        else: by_url[record.source_url] = record
    records = list(by_url.values()); cache_manifest = _read_cache_manifest(args.cache / "manifest.json")
    pages = []
    for url in sorted(discovered_pages):
        matches = [entry for entry in cache_manifest if entry.get("url") == url]
        timestamped = [entry for entry in matches if entry.get("recorded_at")]
        if timestamped:
            pages.append(max(timestamped, key=lambda entry: entry["recorded_at"]))
        elif matches:
            pages.append(matches[-1])
    detail_urls = discovered_pages
    crawled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [{"title": r.title, "paper_code": _paper_code(r.source_url), "abstract": r.abstract or "", "authors": r.authors or "",
             "conference": r.conference, "year": r.year, "source": "CVF", "source_url": r.source_url,
             "keywords": _keywords(r.keywords), "crawled_at": crawled_at, "parser_version": r.parser_version or PARSER_VERSION} for r in records]
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest = {"parser_version": PARSER_VERSION, "events": [_event_entry(event, cache_manifest, skipped, limited) for event in selected], "pages": pages}
    if not args.dry_run:
        _atomic_publish_pair(args.out, _csv_content(rows), manifest_path,
                             json.dumps(manifest, ensure_ascii=False, indent=2))
    result = {"events_seen": len(selected), "event_skipped": sum(item["status"] == "skipped" for item in manifest["events"]),
              "detail_discovered": len(detail_urls), "records_parsed": records_parsed, "duplicates": duplicates,
              "parse_errors": len(failed_pages), "missing_abstract": sum(r.abstract is None for r in records),
              "csv": str(args.out), "manifest": str(manifest_path)}
    print("\n".join(f"{key}={value}" for key, value in result.items())); return result

def main(argv: list[str] | None = None) -> int:
    run(_parser().parse_args(argv)); return 0

if __name__ == "__main__": raise SystemExit(main())
