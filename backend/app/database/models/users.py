"""Application users keyed by the identity managed by Supabase Auth."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import UUID as UUIDType
from sqlalchemy import Column, ForeignKey, MetaData, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base

if TYPE_CHECKING:
    from app.database.models.chat_threads import ChatThread

# Keep Supabase's table outside application metadata so migrations never create it.
auth_users = Table(
    "users",
    MetaData(),
    Column("id", UUIDType, primary_key=True),
    schema="auth",
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        ForeignKey(auth_users.c.id, ondelete="CASCADE"), primary_key=True
    )
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)

    threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
