from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.schemas import ImportSummary, PaperCreate, PaperList, PaperRead, PaperUpdate
from app.services.lookup import LookupUnavailableError, lookup_title
from app.services.papers import (
    DuplicatePaperError,
    create_paper,
    delete_paper,
    get_paper,
    import_csv,
    list_papers,
    update_paper,
)


router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("", response_model=PaperList)
def read_papers(
    q: str | None = None,
    conference: str | None = Query(default=None, pattern="^(CVPR|ICCV|ECCV)$"),
    year: int | None = Query(default=None, ge=1990, le=2100),
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaperList:
    return list_papers(db, q, conference, year, keyword, page, page_size)


@router.get("/lookup", response_model=PaperCreate)
def lookup_paper(title: str = Query(min_length=1), settings=Depends(get_settings)) -> PaperCreate:
    try:
        return lookup_title(title, settings)
    except LookupUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{paper_id}", response_model=PaperRead)
def read_paper(paper_id: int, db: Session = Depends(get_db)) -> PaperRead:
    paper = get_paper(db, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.post("", response_model=PaperRead, status_code=status.HTTP_201_CREATED)
def add_paper(payload: PaperCreate, db: Session = Depends(get_db)) -> PaperRead:
    try:
        return create_paper(db, payload)
    except DuplicatePaperError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/{paper_id}", response_model=PaperRead)
def edit_paper(paper_id: int, payload: PaperUpdate, db: Session = Depends(get_db)) -> PaperRead:
    try:
        paper = update_paper(db, paper_id, payload)
    except DuplicatePaperError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if paper is None:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_paper(paper_id: int, db: Session = Depends(get_db)) -> None:
    if not delete_paper(db, paper_id):
        raise HTTPException(status_code=404, detail="论文不存在")


@router.post("/import", response_model=ImportSummary)
async def import_papers(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportSummary:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="当前仅支持 CSV 文件导入")
    return import_csv(db, await file.read())
