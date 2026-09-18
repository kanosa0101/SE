from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Conference = Literal["CVPR", "ICCV", "ECCV"]


class PaperBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    paper_code: str | None = Field(default=None, max_length=120)
    abstract: str | None = None
    authors: str | None = None
    conference: Conference
    year: int = Field(ge=1990, le=2100)
    source: str = Field(default="manual", max_length=40)
    source_url: str | None = Field(default=None, max_length=1000)
    crawled_at: datetime | None = None
    parser_version: str | None = Field(default=None, max_length=40)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must contain text")
        return value


class PaperCreate(PaperBase):
    pass


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    paper_code: str | None = Field(default=None, max_length=120)
    abstract: str | None = None
    authors: str | None = None
    conference: Conference | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    source_url: str | None = Field(default=None, max_length=1000)
    crawled_at: datetime | None = None
    parser_version: str | None = Field(default=None, max_length=40)
    keywords: list[str] | None = None


class PaperRead(PaperBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normalized_title: str


class PaperList(BaseModel):
    items: list[PaperRead]
    total: int
    page: int
    page_size: int


class ImportItemResult(BaseModel):
    row: int
    title: str | None = None
    status: Literal["created", "skipped", "error"]
    message: str


class ImportSummary(BaseModel):
    total: int
    created: int
    skipped: int
    errors: int
    items: list[ImportItemResult]


class LookupResult(BaseModel):
    found: bool
    source: str | None = None
    paper: PaperCreate | None = None
    message: str
