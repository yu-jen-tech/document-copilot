"""Numbered source excerpts attached to persisted assistant messages."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_messages import ChatMessage
    from app.database.models.document_chunks import DocumentChunk


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint("message_id", "citation_index"),
        CheckConstraint("citation_index > 0", name="positive_citation_index"),
    )

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE")
    )
    # Deleting a filing must not silently erase evidence from chat history.
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="RESTRICT"), index=True
    )
    citation_index: Mapped[int]
    excerpt: Mapped[str] = mapped_column(Text)

    message: Mapped["ChatMessage"] = relationship(back_populates="citations")
    chunk: Mapped["DocumentChunk"] = relationship(back_populates="citations")
