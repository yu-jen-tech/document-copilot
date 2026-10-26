"""Ordered user and assistant messages, UI parts, and generation usage metadata."""

from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_threads import ChatThread
    from app.database.models.message_citations import MessageCitation


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "message_index"),
        CheckConstraint("message_index >= 0", name="nonnegative_message_index"),
        CheckConstraint("role IN ('user', 'assistant')", name="valid_role"),
    )

    thread_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE")
    )
    message_index: Mapped[int]
    role: Mapped[Literal["user", "assistant"]] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    parts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    usage_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb")
    )

    thread: Mapped["ChatThread"] = relationship(back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MessageCitation.citation_index",
    )
