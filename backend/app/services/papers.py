import csv
import io
import re
from collections.abc import Iterable
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import func, insert, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Keyword, Paper, PaperKeyword
from app.schemas import ImportItemResult, ImportSummary, PaperCreate, PaperList, PaperRead, PaperUpdate
from app.services.keywords import (
    canonical_research_area,
    extract_scored_keywords,
    extract_scored_keywords_batch,
    normalize_keyword,
    research_area_for,
)


class DuplicatePaperError(ValueError):
    pass


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _keyword_names(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in (normalize_keyword(value) for value in values) if item))


def _keyword_filter_names(session: Session, value: str, scope: str) -> list[str]:
    normalized = normalize_keyword(value)
    if scope != "area":
        return [normalized]
    area = canonical_research_area(normalized)
    if area is None:
        return []
    return [
        name
        for name in session.scalars(select(Keyword.name)).all()
        if research_area_for(name) == area
    ]


def _replace_keywords(
    session: Session,
    paper: Paper,
    values: list[str],
    keyword_cache: dict[str, Keyword] | None = None,
) -> None:
    if paper.id is not None:
        session.query(PaperKeyword).filter(PaperKeyword.paper_id == paper.id).delete(synchronize_session=False)
    scored_keywords = extract_scored_keywords(paper.title, paper.abstract, values)
    resolved_keywords = keyword_cache if keyword_cache is not None else {}
    for name, _score, _method in scored_keywords:
        keyword = resolved_keywords.get(name)
        if keyword is None:
            keyword = session.scalar(select(Keyword).where(Keyword.name == name))
        if keyword is None:
            keyword = Keyword(name=name)
            session.add(keyword)
        resolved_keywords[name] = keyword
    for name, score, method in scored_keywords:
        keyword = resolved_keywords[name]
        session.add(PaperKeyword(paper=paper, keyword=keyword, score=score, method=method))


def serialize_paper(paper: Paper) -> PaperRead:
    return PaperRead.model_validate(
        {
            "id": paper.id,
            "title": paper.title,
            "normalized_title": paper.normalized_title,
            "paper_code": paper.paper_code,
            "abstract": paper.abstract,
            "authors": paper.authors,
            "conference": paper.conference,
            "year": paper.year,
            "source": paper.source,
            "source_url": paper.source_url,
            "crawled_at": paper.crawled_at,
            "parser_version": paper.parser_version,
            "keywords": [relation.keyword.name for relation in paper.paper_keywords],
        }
    )


def _add_paper(
    session: Session,
    payload: PaperCreate,
    *,
    keyword_cache: dict[str, Keyword] | None = None,
    check_duplicate: bool = True,
) -> Paper:
    values = payload.model_dump()
    keywords = _keyword_names(values.pop("keywords", []))
    values["normalized_title"] = normalize_title(values["title"])
    if check_duplicate:
        duplicate = session.scalar(
            select(Paper).where(
                Paper.normalized_title == values["normalized_title"],
                Paper.conference == values["conference"],
                Paper.year == values["year"],
            )
        )
        if duplicate is not None:
            raise DuplicatePaperError("相同会议、年份和标题的论文已存在")
    paper = Paper(**values)
    session.add(paper)
    _replace_keywords(session, paper, keywords, keyword_cache)
    return paper


def create_paper(session: Session, payload: PaperCreate) -> PaperRead:
    try:
        paper = _add_paper(session, payload)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicatePaperError("论文记录与已有数据重复") from exc
    session.refresh(paper)
    return serialize_paper(paper)


def get_paper(session: Session, paper_id: int) -> PaperRead | None:
    paper = session.get(Paper, paper_id)
    return serialize_paper(paper) if paper else None


def list_papers(
    session: Session,
    q: str | None,
    conference: str | None,
    year: int | None,
    keyword: str | None,
    page: int,
    page_size: int,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    keyword_scope: str = "keyword",
) -> PaperList:
    query = select(Paper)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.outerjoin(PaperKeyword).outerjoin(Keyword).where(
            or_(
                Paper.title.ilike(pattern),
                Paper.paper_code.ilike(pattern),
                Paper.authors.ilike(pattern),
                Keyword.name.ilike(pattern),
            )
        ).distinct()
    if conference:
        query = query.where(Paper.conference == conference)
    if year:
        query = query.where(Paper.year == year)
    if year_from is not None:
        query = query.where(Paper.year >= year_from)
    if year_to is not None:
        query = query.where(Paper.year <= year_to)
    if keyword:
        names = _keyword_filter_names(session, keyword, keyword_scope)
        query = query.where(
            Paper.paper_keywords.any(
                PaperKeyword.keyword.has(Keyword.name.in_(names))
            )
        )
    count = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(Paper.year.desc(), Paper.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return PaperList(
        items=[serialize_paper(row) for row in rows], total=count, page=page, page_size=page_size
    )


def update_paper(session: Session, paper_id: int, payload: PaperUpdate) -> PaperRead | None:
    paper = session.get(Paper, paper_id)
    if paper is None:
        return None
    values = payload.model_dump(exclude_unset=True)
    keyword_values = values.pop("keywords", None)
    for name, value in values.items():
        setattr(paper, name, value)
    if "title" in values:
        paper.normalized_title = normalize_title(paper.title)
    if any(name in values for name in ("title", "conference", "year")):
        duplicate = session.scalar(
            select(Paper).where(
                Paper.id != paper.id,
                Paper.normalized_title == paper.normalized_title,
                Paper.conference == paper.conference,
                Paper.year == paper.year,
            )
        )
        if duplicate is not None:
            raise DuplicatePaperError("修改后会与已有论文重复")
    if keyword_values is not None:
        _replace_keywords(session, paper, _keyword_names(keyword_values))
    session.commit()
    session.refresh(paper)
    return serialize_paper(paper)


def delete_paper(session: Session, paper_id: int) -> bool:
    paper = session.get(Paper, paper_id)
    if paper is None:
        return False
    session.delete(paper)
    session.commit()
    return True


def _parse_crawled_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid crawled_at timestamp: {value}") from exc


def _payload_from_row(row: dict[str, str], default_source: str = "csv") -> PaperCreate:
    raw_keywords = row.get("keywords", "") or ""
    keywords = [value.strip() for value in re.split(r"[|,;]", raw_keywords) if value.strip()]
    return PaperCreate(
        title=row.get("title", ""),
        paper_code=row.get("paper_code") or None,
        abstract=row.get("abstract") or None,
        authors=row.get("authors") or None,
        conference=row.get("conference", "CVPR"),
        year=int(row.get("year", "0")),
        source=row.get("source") or default_source,
        source_url=row.get("source_url") or None,
        crawled_at=_parse_crawled_at(row.get("crawled_at")),
        parser_version=row.get("parser_version") or None,
        keywords=keywords,
    )


def _bulk_add_papers(session: Session, payloads: list[PaperCreate]) -> None:
    if not payloads:
        return

    paper_rows: list[dict[str, object]] = []
    keywords_by_identity: dict[tuple[str, str, int], list[tuple[str, float, str]]] = {}
    keyword_names: set[str] = set()
    extracted_keywords = extract_scored_keywords_batch(
        [(payload.title, payload.abstract, payload.keywords) for payload in payloads]
    )
    for payload, scored in zip(payloads, extracted_keywords, strict=True):
        identity = (normalize_title(payload.title), payload.conference, payload.year)
        paper_rows.append(
            payload.model_dump(exclude={"keywords"})
            | {"normalized_title": identity[0]}
        )
        keywords_by_identity[identity] = scored
        keyword_names.update(name for name, _score, _method in scored)

    existing_keyword_names = set(session.scalars(select(Keyword.name)).all())
    new_keyword_names = sorted(keyword_names - existing_keyword_names)
    if new_keyword_names:
        session.execute(insert(Keyword), [{"name": name} for name in new_keyword_names])
    session.execute(insert(Paper), paper_rows)

    paper_ids = {
        (normalized_title, conference, year): paper_id
        for paper_id, normalized_title, conference, year in session.execute(
            select(Paper.id, Paper.normalized_title, Paper.conference, Paper.year)
        ).all()
    }
    keyword_ids = dict(session.execute(select(Keyword.name, Keyword.id)).all())
    relations = []
    for identity, scored in keywords_by_identity.items():
        paper_id = paper_ids[identity]
        relations.extend(
            {
                "paper_id": paper_id,
                "keyword_id": keyword_ids[name],
                "score": score,
                "method": method,
            }
            for name, score, method in scored
        )
    if relations:
        session.execute(insert(PaperKeyword), relations)


def import_csv(session: Session, content: bytes, *, strict: bool = False) -> ImportSummary:
    decoded = content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(decoded)))
    result_by_row: dict[int, ImportItemResult] = {}
    pending: list[tuple[int, str | None, PaperCreate]] = []
    identity_keys = {
        (normalized_title, conference, year)
        for normalized_title, conference, year in session.execute(
            select(Paper.normalized_title, Paper.conference, Paper.year)
        ).all()
    }
    for index, row in enumerate(rows, start=2):
        title = (row.get("title") or "").strip() or None
        try:
            payload = _payload_from_row(row)
            identity = (normalize_title(payload.title), payload.conference, payload.year)
            if identity in identity_keys:
                result_by_row[index] = ImportItemResult(row=index, title=title, status="skipped", message="记录已存在")
                continue
            identity_keys.add(identity)
            pending.append((index, title, payload))
        except (ValidationError, ValueError, DuplicatePaperError) as exc:
            if strict:
                raise
            result_by_row[index] = ImportItemResult(row=index, title=title, status="error", message=str(exc))
    _bulk_add_papers(session, [payload for _index, _title, payload in pending])
    session.commit()
    for index, title, _payload in pending:
        result_by_row[index] = ImportItemResult(row=index, title=title, status="created", message="已入库")
    results = [result_by_row[index] for index in range(2, len(rows) + 2)]
    created = sum(item.status == "created" for item in results)
    skipped = sum(item.status == "skipped" for item in results)
    errors = sum(item.status == "error" for item in results)
    return ImportSummary(total=len(rows), created=created, skipped=skipped, errors=errors, items=results)


def export_papers(
    session: Session,
    export_format: str,
    q: str | None,
    conference: str | None,
    year: int | None,
    keyword: str | None,
    *,
    year_from: int | None = None,
    year_to: int | None = None,
    keyword_scope: str = "keyword",
) -> tuple[bytes, str]:
    query = select(Paper).order_by(Paper.year.desc(), Paper.id.asc())
    if q:
        pattern = f"%{q.strip()}%"
        query = query.outerjoin(PaperKeyword).outerjoin(Keyword).where(
            or_(Paper.title.ilike(pattern), Paper.paper_code.ilike(pattern), Paper.authors.ilike(pattern), Keyword.name.ilike(pattern))
        ).distinct()
    if conference:
        query = query.where(Paper.conference == conference)
    if year:
        query = query.where(Paper.year == year)
    if year_from is not None:
        query = query.where(Paper.year >= year_from)
    if year_to is not None:
        query = query.where(Paper.year <= year_to)
    if keyword:
        keyword_names = _keyword_filter_names(session, keyword, keyword_scope)
        if q:
            query = query.where(
                Paper.paper_keywords.any(
                    PaperKeyword.keyword.has(Keyword.name.in_(keyword_names))
                )
            )
        else:
            query = query.where(
                Paper.paper_keywords.any(
                    PaperKeyword.keyword.has(Keyword.name.in_(keyword_names))
                )
            )
    papers = session.scalars(query).unique().all()
    if export_format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["title", "authors", "conference", "year", "abstract", "keywords", "source", "source_url"])
        for paper in papers:
            writer.writerow([paper.title, paper.authors or "", paper.conference, paper.year, paper.abstract or "", "|".join(sorted(relation.keyword.name for relation in paper.paper_keywords)), paper.source, paper.source_url or ""])
        return output.getvalue().encode("utf-8"), "text/csv; charset=utf-8"
    output = io.StringIO()
    used_keys: dict[str, int] = {}
    for paper in papers:
        author = (paper.authors or "Unknown").split(",", 1)[0].strip().split()
        surname = re.sub(r"[^A-Za-z0-9]", "", author[-1] if author else "Unknown") or "Unknown"
        title_key = re.sub(r"[^A-Za-z0-9]", "", paper.title)
        base_key = f"{surname}{paper.year}{title_key}"
        used_keys[base_key] = used_keys.get(base_key, 0) + 1
        key = base_key if used_keys[base_key] == 1 else f"{base_key}{used_keys[base_key]}"
        def escape(value: str) -> str:
            replacements = {
                "\\": r"\textbackslash{}",
                "{": r"\{",
                "}": r"\}",
                "%": r"\%",
                "_": r"\_",
                "&": r"\&",
                "#": r"\#",
                "$": r"\$",
                "^": r"\^{}",
                "~": r"\~{}",
            }
            value = value.replace("\r\n", "\n").replace("\r", "\n")
            return "".join(replacements.get(character, " " if character == "\n" else character) for character in value)
        output.write(f"@inproceedings{{{key},\n")
        output.write(f"  title = {{{escape(paper.title)}}},\n")
        if paper.authors:
            output.write(f"  author = {{{escape(paper.authors)}}},\n")
        output.write(f"  booktitle = {{{escape(paper.conference)}}},\n  year = {{{paper.year}}},\n")
        if paper.abstract:
            output.write(f"  abstract = {{{escape(paper.abstract)}}},\n")
        output.write("}\n\n")
    return output.getvalue().encode("utf-8"), "application/x-bibtex; charset=utf-8"
