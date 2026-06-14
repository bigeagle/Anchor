"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anchor_server.database import Base
from anchor_server.enums import ItemType


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


class Item(Base):
    """A bibliographic item (paper, book, etc.)."""

    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default=ItemType.JOURNAL_ARTICLE.value
    )
    authors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication: Mapped[str | None] = mapped_column(String(512), nullable=True)
    volume: Mapped[str | None] = mapped_column(String(64), nullable=True)
    issue: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(128), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    date_added: Mapped[datetime] = mapped_column(default=utc_now)
    date_modified: Mapped[datetime] = mapped_column(
        default=utc_now,
        onupdate=utc_now,
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Attachment(Base):
    """A file attached to an item."""

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    date_added: Mapped[datetime] = mapped_column(default=utc_now)

    item: Mapped["Item"] = relationship(back_populates="attachments")
