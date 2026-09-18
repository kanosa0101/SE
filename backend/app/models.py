from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (UniqueConstraint("normalized_title", "conference", "year", name="uq_paper_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    paper_code: Mapped[str | None] = mapped_column(String(120))
    abstract: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[str | None] = mapped_column(Text)
    conference: Mapped[str] = mapped_column(String(10), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    paper_keywords: Mapped[list["PaperKeyword"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

    paper_keywords: Mapped[list["PaperKeyword"]] = relationship(back_populates="keyword")


class PaperKeyword(Base):
    __tablename__ = "paper_keywords"
    __table_args__ = (UniqueConstraint("paper_id", "keyword_id", name="uq_paper_keyword"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="provided")

    paper: Mapped[Paper] = relationship(back_populates="paper_keywords")
    keyword: Mapped[Keyword] = relationship(back_populates="paper_keywords")
