"""Pydantic schemas for API request/response validation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from anchor_server.enums import ItemType


class AttachmentOut(BaseModel):
    """Attachment representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    filename: str
    content_type: str | None
    size: int
    date_added: datetime


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
    attachments: list[AttachmentOut] = Field(default_factory=list)
