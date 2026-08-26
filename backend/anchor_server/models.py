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
    # Path (relative to settings.notes_dir) of the linked Obsidian-style
    # markdown note; the file itself travels out-of-band like attachments.
    note_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    date_added: Mapped[datetime] = mapped_column(default=utc_now)
    date_modified: Mapped[datetime] = mapped_column(
        default=utc_now,
        onupdate=utc_now,
    )
    # Sync groundwork: bumped on every local mutation; tombstone on delete.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

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
    # Sync groundwork: bumped on every local mutation; tombstone on delete.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    item: Mapped["Item"] = relationship(back_populates="attachments")


class OutboxEntry(Base):
    """One pending local change waiting to be pushed to the central server.

    Device-local only; entries are deleted once the central acknowledges them.
    """

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    op: Mapped[str] = mapped_column(String(16), nullable=False)  # upsert | delete
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class SyncState(Base):
    """Single-row device sync state: identity, pull cursor, and halt flag.

    The pull cursor (`last_seq`, `last_checksum`) must commit in the same
    transaction as the applied changes, so it lives in the same database,
    not a state file. `last_error` halts syncing: "cursor_mismatch" until
    the row is deleted (manual re-anchor), "protocol_mismatch" only until
    the central reports a matching protocol version again (auto-recovery).
    """

    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    device_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SyncMeta(Base):
    """Single-row central metadata: the instance id anchoring the oplog chain."""

    __tablename__ = "sync_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    instance_id: Mapped[str] = mapped_column(String(64), nullable=False)


class ChangeEntry(Base):
    """One applied change in the central oplog.

    ``seq`` is the global ordering assigned by the central server; devices
    pull entries newer than their local cursor and apply them idempotently.
    ``checksum`` chains each entry to its predecessor (and the first entry to
    the central's ``instance_id``), letting devices verify they are following
    the same oplog chain before applying an increment.
    """

    __tablename__ = "changes"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    op: Mapped[str] = mapped_column(String(16), nullable=False)  # upsert | delete
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    origin_device: Mapped[str] = mapped_column(String(64), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class ApiToken(Base):
    """SHA-256 hash of an owner API token used for Bearer authentication."""

    __tablename__ = "api_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class ConnectorSession(Base):
    """Temporary session state for a Zotero Connector save flow.

    Maps connector-side IDs (sessionID, itemID, attachmentID strings) to Anchor
    UUIDs across the multi-request save sequence.
    """

    __tablename__ = "connector_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    item_map: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    attachment_map: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    pending_attachments: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        default=utc_now,
        onupdate=utc_now,
    )
