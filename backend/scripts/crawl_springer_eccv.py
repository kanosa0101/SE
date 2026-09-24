"""Create the ECCV supplement CSV from Springer chapter metadata."""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crawlers.springer_eccv import (  # noqa: E402
    CSV_FIELDS,
    PARSER_VERSION,
    SEED_BOOKS,
    SpringerEccvCrawler,
    is_chapter_doi,
    record_to_csv_row,
    records_from_cache,
    fetch_semantic_scholar_abstracts,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, choices=sorted(SEED_BOOKS),
                        default=sorted(SEED_BOOKS))
    parser.add_argument("--out", type=Path,
                        default=ROOT_DIR / "data" / "eccv_supplement.csv")
    parser.add_argument("--cache", type=Path,
                        default=ROOT_DIR / "data" / "raw" / "springer_eccv")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--workers", type=_positive_int, default=4)
    parser.add_argument("--limit", type=_positive_int,
                        help="optional paper limit for a small trial run")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cache-only", action="store_true",
                      help="export only responses already present in the cache; do not access the network")
    mode.add_argument("--fill-missing-abstracts", action="store_true",
                      help="fetch abstracts only for cached records that currently lack one")
    parser.add_argument("--resume-csv", type=Path,
                        help="resume abstract backfill from an existing CSV without scanning the full cache")
    parser.add_argument("--springer-fallback", action="store_true",
                        help="also retry unresolved papers individually through Springer Reader")
    parser.add_argument("--skip-semantic-scholar", action="store_true",
                        help="reuse existing cached abstracts without making a batch API request")
    return parser


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fill_missing_abstracts(records, crawler, workers: int, target_dois: set[str]):
    missing = [
        record for record in records
        if not record.get("abstract") and str(record["doi"]).casefold() in target_dois
    ]
    if not missing:
        return records, 0, 0

    updated: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(crawler.fetch_paper, record) for record in missing]
        found = 0
        for checked, future in enumerate(as_completed(futures), start=1):
            fetched = future.result()
            doi = str(fetched["doi"]).casefold()
            if fetched.get("abstract"):
                updated[doi] = fetched
                found += 1
            if checked % 100 == 0 or checked == len(futures):
                print(f"abstracts_checked={checked}/{len(futures)}; newly_found={found}", flush=True)

    merged = []
    for record in records:
        fetched = updated.get(str(record["doi"]).casefold())
        if fetched:
            merged.append({**record, "abstract": fetched["abstract"], "source": fetched["source"]})
        else:
            merged.append(record)
    return merged, len(missing), found


def _records_from_csv(path: Path) -> list[dict[str, object]]:
    records = []
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            source_path = urlparse(row.get("source_url") or "").path
            marker = "/chapter/"
            doi = unquote(source_path.split(marker, 1)[-1]) if marker in source_path else ""
            if not is_chapter_doi(doi):
                raise ValueError(f"invalid Springer chapter URL in CSV row {row_number}")
            records.append({
                **row,
                "doi": doi,
                "year": int(row["year"]),
                "abstract": row.get("abstract") or None,
                "authors": [value.strip() for value in (row.get("authors") or "").split(";") if value.strip()],
                "keywords": [value.strip() for value in (row.get("keywords") or "").split(";") if value.strip()],
                "abstract_inverted_index": None,
            })
    return records


def run(args: argparse.Namespace, crawler_factory=None) -> dict[str, object]:
    attempted = 0
    added = 0
    targeted = 0
    semantic_scholar_added = 0
    deferred = 0
    if args.cache_only:
        records = records_from_cache(args.cache, args.years)
        if args.limit is not None:
            records = records[:args.limit]
    elif args.fill_missing_abstracts:
        records = _records_from_csv(args.resume_csv) if args.resume_csv else records_from_cache(args.cache, args.years)
        missing_before = sum(not record.get("abstract") for record in records)
        if missing_before:
            targets = [
                record for record in records
                if not record.get("abstract") and int(record["year"]) in args.years
            ]
            if args.limit is not None:
                targets = targets[:args.limit]
            targeted = len(targets)
            target_dois = {str(record["doi"]).casefold() for record in targets}
            batch_abstracts = {} if args.skip_semantic_scholar else fetch_semantic_scholar_abstracts(
                [str(record["doi"]) for record in targets], args.cache
            )
            for record in records:
                doi = str(record["doi"]).casefold()
                if doi in target_dois and doi in batch_abstracts:
                    record["abstract"] = batch_abstracts[doi]
                    record["source"] = "Semantic Scholar"
                    added += 1
            semantic_scholar_added = added
            print(f"semantic_scholar_abstracts_found={added}", flush=True)

            records_by_doi = {str(record["doi"]).casefold(): record for record in records}
            remaining_dois = {
                doi for doi in target_dois
                if not records_by_doi[doi].get("abstract")
            }
            if remaining_dois and args.springer_fallback:
                crawler_factory = crawler_factory or SpringerEccvCrawler
                with crawler_factory(
                    args.cache, timeout=args.timeout, max_retries=args.max_retries,
                    delay=max(args.delay, 3.0), workers=args.workers,
                ) as crawler:
                    records, attempted, fallback_added = _fill_missing_abstracts(
                        records, crawler, args.workers, remaining_dois
                    )
                added += fallback_added
            else:
                deferred = len(remaining_dois)
    else:
        crawler_factory = crawler_factory or SpringerEccvCrawler
        with crawler_factory(
            args.cache, timeout=args.timeout, max_retries=args.max_retries, delay=args.delay,
            workers=args.workers,
        ) as crawler:
            records = crawler.crawl(args.years, limit=args.limit)

    crawled_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = [record_to_csv_row(record, crawled_at) for record in records]
    _write_csv(args.out, rows)
    result = {
        "years": ",".join(str(year) for year in args.years),
        "records": len(rows),
        "missing_abstract": sum(not row["abstract"] for row in rows),
        "parser_version": PARSER_VERSION,
        "cache_only": args.cache_only,
        "csv": str(args.out),
    }
    if args.fill_missing_abstracts:
        result["abstracts_attempted"] = targeted
        result["abstracts_added"] = added
        result["semantic_scholar_added"] = semantic_scholar_added
        result["fallback_attempted"] = attempted
        result["fallback_deferred"] = deferred
        result["missing_abstracts_before"] = missing_before
    print("\n".join(f"{key}={value}" for key, value in result.items()))
    return result


def main(argv: list[str] | None = None) -> int:
    run(_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
