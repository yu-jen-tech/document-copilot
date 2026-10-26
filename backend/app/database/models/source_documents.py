"""SEC filing metadata and the normalized Markdown used for ingestion."""

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Date, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.document_chunks import DocumentChunk


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        CheckConstraint("year > 0", name="positive_year"),
        Index("ix_source_documents_ticker_year", "ticker", "year"),
    )

    ticker: Mapped[str] = mapped_column(Text)
    company_name: Mapped[str] = mapped_column(Text)
    cik: Mapped[str] = mapped_column(Text)
    filing_type: Mapped[str] = mapped_column(Text)
    filing_date: Mapped[date] = mapped_column(Date)
    report_date: Mapped[date | None] = mapped_column(Date)
    year: Mapped[int]
    accession_number: Mapped[str] = mapped_column(Text, unique=True)
    source_url: Mapped[str] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text)
    # DeclarativeBase reserves the Python attribute name "metadata".
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )
