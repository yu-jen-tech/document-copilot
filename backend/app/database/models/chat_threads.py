"""Conversation ownership and thread metadata."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_messages import ChatMessage
    from app.database.models.users import User


class ChatThread(Base):
    __tablename__ = "chat_threads"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text, server_default=text("'New chat'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="threads")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.message_index",
    )
