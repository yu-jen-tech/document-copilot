"""Retrieval passages with vector embeddings and generated lexical search data."""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.message_citations import MessageCitation
    from app.database.models.source_documents import SourceDocument


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        CheckConstraint("chunk_index >= 0", name="nonnegative_chunk_index"),
        CheckConstraint("token_count > 0", name="positive_token_count"),
        CheckConstraint("page IS NULL OR page > 0", name="positive_page"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_documents.id", ondelete="CASCADE")
    )
    chunk_index: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int]
    page: Mapped[int | None]
    section: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    # Dimensions are part of the schema; changing them requires a migration.
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1536))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english'::regconfig, content)", persisted=True),
    )

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")
    citations: Mapped[list["MessageCitation"]] = relationship(
        back_populates="chunk", passive_deletes="all"
    )
