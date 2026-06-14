"""Pydantic schemas for Zotero Connector payloads and responses."""

from typing import Any

from pydantic import BaseModel, Field


class ConnectorPingResponse(BaseModel):
    """Response to /connector/ping."""

    prefs: dict[str, Any]


class ConnectorCollectionResponse(BaseModel):
    """Response to /connector/getSelectedCollection."""

    id: str = "default"
    name: str = "My Library"
    libraryEditable: bool = True
    filesEditable: bool = True
    targets: list[dict[str, Any]] = Field(default_factory=list)
    tags: dict[str, Any] = Field(default_factory=dict)


class ConnectorAttachment(BaseModel):
    """Attachment descriptor inside a Zotero item payload."""

    id: str
    parentItem: str
    title: str
    url: str | None = None
    mimeType: str | None = None
    snapshot: bool = False


class ConnectorItem(BaseModel):
    """A single item from a Zotero translator payload."""

    id: str
    itemType: str
    title: str | None = None
    url: str | None = None
    DOI: str | None = None
    ISBN: str | None = None
    arxivID: str | None = None
    archiveID: str | None = None
    abstractNote: str | None = None
    publicationTitle: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    date: str | None = None
    year: int | None = None
    language: str | None = None
    extra: str | None = None
    creators: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[ConnectorAttachment] = Field(default_factory=list)


class ConnectorSaveItemsRequest(BaseModel):
    """Payload for /connector/saveItems."""

    sessionID: str
    uri: str | None = None
    proxy: dict[str, Any] | None = None
    cookie: str | None = None
    detailedCookies: str | None = None
    items: list[ConnectorItem]


class ConnectorSessionProgressRequest(BaseModel):
    """Payload for /connector/sessionProgress."""

    sessionID: str


class ConnectorSessionProgressResponse(BaseModel):
    """Response for /connector/sessionProgress."""

    items: list[dict[str, Any]] = Field(default_factory=list)
    done: bool = False


class ConnectorSaveSnapshotRequest(BaseModel):
    """Payload for /connector/saveSnapshot."""

    sessionID: str
    url: str
    referrer: str | None = None
    cookie: str | None = None
    detailedCookies: str | None = None
    title: str | None = None
    pdf: bool = False
    skipSnapshot: bool = False
    singleFile: bool = False


class ConnectorSaveSingleFileRequest(BaseModel):
    """Payload for /connector/saveSingleFile."""

    items: list[ConnectorItem] = Field(default_factory=list)
    sessionID: str
    snapshotContent: str
    url: str
    title: str | None = None


class ConnectorSaveAttachmentMetadata(BaseModel):
    """Metadata carried in the X-Metadata header for attachment uploads."""

    id: str
    url: str | None = None
    contentType: str | None = None
    parentItemID: str | None = None
    title: str | None = None


class ConnectorStandaloneAttachmentMetadata(BaseModel):
    """Metadata for a standalone attachment upload."""

    url: str | None = None
    contentType: str | None = None
    title: str | None = None


class ConnectorStandaloneAttachmentResponse(BaseModel):
    """Response for /connector/saveStandaloneAttachment."""

    canRecognize: bool = False
