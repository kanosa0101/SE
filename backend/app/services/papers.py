import csv
import io
import re
from collections.abc import Iterable
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Keyword, Paper, PaperKeyword
from app.schemas import ImportItemResult, ImportSummary, PaperCreate, PaperList, PaperRead, PaperUpdate
from app.services.keywords import extract_scored_keywords, normalize_keyword


class DuplicatePaperError(ValueError):
    pass


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _keyword_names(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in (normalize_keyword(value) for value in values) if item))


def _replace_keywords(session: Session, paper: Paper, values: list[str]) -> None:
    session.query(PaperKeyword).filter(PaperKeyword.paper_id == paper.id).delete(synchronize_session=False)
    for name, score, method in extract_scored_keywords(paper.title, paper.abstract, values):
        keyword = session.scalar(select(Keyword).where(Keyword.name == name))
        if keyword is None:
            keyword = Keyword(name=name)
            session.add(keyword)
            session.flush()
        session.add(PaperKeyword(paper_id=paper.id, keyword_id=keyword.id, score=score, method=method))


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


def create_paper(session: Session, payload: PaperCreate) -> PaperRead:
    values = payload.model_dump()
    keywords = _keyword_names(values.pop("keywords", []))
    values["normalized_title"] = normalize_title(values["title"])
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
    try:
        session.flush()
        _replace_keywords(session, paper, keywords)
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
        query = query.join(PaperKeyword).join(Keyword).where(Keyword.name == normalize_keyword(keyword))
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


def import_csv(session: Session, content: bytes) -> ImportSummary:
    decoded = content.decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(decoded))
    results: list[ImportItemResult] = []
    created = skipped = errors = 0
    for index, row in enumerate(rows, start=2):
        title = (row.get("title") or "").strip() or None
        try:
            payload = _payload_from_row(row)
            existing = session.scalar(
                select(Paper).where(
                    Paper.normalized_title == normalize_title(payload.title),
                    Paper.conference == payload.conference,
                    Paper.year == payload.year,
                )
            )
            if existing:
                skipped += 1
                results.append(ImportItemResult(row=index, title=title, status="skipped", message="记录已存在"))
                continue
            create_paper(session, payload)
            created += 1
            results.append(ImportItemResult(row=index, title=title, status="created", message="已入库"))
        except (ValidationError, ValueError, DuplicatePaperError) as exc:
            session.rollback()
            errors += 1
            results.append(ImportItemResult(row=index, title=title, status="error", message=str(exc)))
    return ImportSummary(total=created + skipped + errors, created=created, skipped=skipped, errors=errors, items=results)


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
        normalized_keyword = normalize_keyword(keyword)
        if q:
            query = query.where(
                Paper.paper_keywords.any(
                    PaperKeyword.keyword.has(Keyword.name == normalized_keyword)
                )
            )
        else:
            query = query.join(PaperKeyword).join(Keyword).where(Keyword.name == normalized_keyword)
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
