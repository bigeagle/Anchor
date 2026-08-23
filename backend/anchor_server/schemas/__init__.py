"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from anchor_server.config import settings
from anchor_server.enums import ItemType


class AttachmentOut(BaseModel):
    """Attachment representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    filename: str
    content_type: str | None
    size: int
    storage_path: str
    date_added: datetime
    version: int

    @computed_field
    @property
    def href(self) -> str:
        """Relative download URL; prepend the API base URL (e.g. /api/v1)."""
        return f"/attachments/{self.id}"

    @computed_field
    @property
    def available(self) -> bool:
        """Whether the file exists locally yet (Syncthing may still deliver it)."""
        return (settings.attachments_dir / self.storage_path).is_file()

    @computed_field
    @property
    def size_mismatch(self) -> bool:
        """True when a local file exists but its size differs from metadata.

        A cheap detector for Syncthing filename collisions (same rendered
        name, different content saved on two devices while offline).
        """
        path = settings.attachments_dir / self.storage_path
        return path.is_file() and path.stat().st_size != self.size


class ItemBase(BaseModel):
    """Shared bibliographic fields."""

    title: str = Field(..., min_length=1)
    item_type: ItemType = Field(default=ItemType.JOURNAL_ARTICLE)
    authors: list[dict[str, Any]] = Field(default_factory=list)
    abstract: str | None = None
    publication: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    url: str | None = None
    language: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ItemCreate(ItemBase):
    """Schema for creating a new item."""


class ItemUpdate(BaseModel):
    """Schema for updating an existing item; all fields are optional."""

    title: str | None = Field(default=None, min_length=1)
    item_type: ItemType | None = None
    authors: list[dict[str, Any]] | None = None
    abstract: str | None = None
    publication: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    year: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    url: str | None = None
    language: str | None = None
    extra: dict[str, Any] | None = None


class ItemOut(ItemBase):
    """Full item representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_added: datetime
    date_modified: datetime
    version: int
    attachments: list[AttachmentOut] = Field(default_factory=list)

    @field_validator("attachments", mode="before")
    @classmethod
    def _drop_deleted_attachments(cls, value: Any) -> Any:
        """Exclude soft-deleted attachments loaded through the ORM relationship."""
        return [a for a in value if getattr(a, "deleted_at", None) is None]
