"""Zotero Connector save orchestration and session management."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from anchor_server.models import Attachment, ConnectorSession, Item
from anchor_server.schemas.zotero import (
    ConnectorSaveAttachmentMetadata,
    ConnectorSaveItemsRequest,
    ConnectorSaveSingleFileRequest,
    ConnectorSaveSnapshotRequest,
    ConnectorStandaloneAttachmentMetadata,
)
from anchor_server.services import import_service, storage


def get_or_create_session(db: Session, session_id: str) -> ConnectorSession:
    """Fetch an existing connector session or create a new one."""
    session = (
        db.query(ConnectorSession)
        .filter(ConnectorSession.session_id == session_id)
        .first()
    )
    if session is None:
        session = ConnectorSession(session_id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _save_session(session: ConnectorSession, db: Session) -> None:
    """Mark the SQLAlchemy session object as updated and commit."""
    db.commit()
    db.refresh(session)


def save_items(db: Session, payload: ConnectorSaveItemsRequest) -> dict[str, Any]:
    """Create Anchor items from a connector payload and record the session map."""
    session = get_or_create_session(db, payload.sessionID)

    pending_attachments: list[str] = []
    item_map = dict(session.item_map)

    for connector_item in payload.items:
        item = import_service.map_connector_item_to_item(connector_item)
        db.add(item)
        db.flush()  # assign item.id
        item_map[connector_item.id] = str(item.id)

        # In the modern workflow, only link-style attachments are listed here.
        # Binary attachments are uploaded separately via saveAttachment.
        for attachment in connector_item.attachments:
            if not attachment.snapshot and attachment.mimeType not in (
                "application/pdf",
                "application/epub+zip",
            ):
                continue
            pending_attachments.append(attachment.id)

    session.item_map = item_map
    session.pending_attachments = list(
        set(session.pending_attachments) | set(pending_attachments)
    )
    _save_session(session, db)
    return {}


def save_attachment(
    db: Session,
    session_id: str,
    metadata: ConnectorSaveAttachmentMetadata,
    data: bytes,
) -> dict[str, Any]:
    """Store a binary attachment uploaded by the connector and link it to its parent item."""
    session = get_or_create_session(db, session_id)
    parent_id_str = metadata.parentItemID
    if not parent_id_str or parent_id_str not in session.item_map:
        raise ValueError("Parent item not found in connector session")

    item_id = uuid.UUID(session.item_map[parent_id_str])
    item = db.get(Item, item_id)
    if item is None:
        raise ValueError("Parent item not found")

    filename = _safe_filename(metadata.title or "attachment", metadata.contentType)
    storage_path = storage.save_attachment(item, filename, metadata.contentType, data)

    attachment = Attachment(
        item_id=item_id,
        filename=storage_path.split("/")[-1],
        content_type=metadata.contentType,
        size=len(data),
        storage_path=storage_path,
    )
    db.add(attachment)
    db.flush()

    attachment_map = dict(session.attachment_map)
    attachment_map[metadata.id] = str(attachment.id)
    session.attachment_map = attachment_map

    pending = list(session.pending_attachments)
    if metadata.id in pending:
        pending.remove(metadata.id)
    session.pending_attachments = pending

    _save_session(session, db)
    return {}


def save_standalone_attachment(
    db: Session,
    session_id: str,
    metadata: ConnectorStandaloneAttachmentMetadata,
    data: bytes,
) -> dict[str, Any]:
    """Create a parent item for a standalone attachment and store the file."""
    session = get_or_create_session(db, session_id)

    item = Item(
        title=metadata.title or metadata.url or "Untitled",
        item_type="document",
        url=metadata.url,
    )
    db.add(item)
    db.flush()

    # Register the new item in the session map so progress can reference it.
    standalone_key = metadata.url or metadata.title or "standalone"
    item_map = dict(session.item_map)
    item_map[standalone_key] = str(item.id)
    session.item_map = item_map

    filename = _safe_filename(metadata.title or "attachment", metadata.contentType)
    storage_path = storage.save_attachment(item, filename, metadata.contentType, data)

    attachment = Attachment(
        item_id=item.id,
        filename=storage_path.split("/")[-1],
        content_type=metadata.contentType,
        size=len(data),
        storage_path=storage_path,
    )
    db.add(attachment)
    db.flush()

    _save_session(session, db)
    return {"canRecognize": False}


def save_single_file(
    db: Session, payload: ConnectorSaveSingleFileRequest
) -> dict[str, Any]:
    """Store a SingleFile HTML snapshot as an attachment."""
    session = get_or_create_session(db, payload.sessionID)

    # Prefer the first item from the payload; otherwise look up the session.
    parent_key = payload.items[0].id if payload.items else None
    item_id: uuid.UUID | None = None
    if parent_key and parent_key in session.item_map:
        item_id = uuid.UUID(session.item_map[parent_key])
    else:
        # Fallback: create a webpage item for the snapshot.
        item = Item(
            title=payload.title or payload.url,
            item_type="webpage",
            url=payload.url,
        )
        db.add(item)
        db.flush()
        item_id = item.id

    item = db.get(Item, item_id)
    if item is None:
        raise ValueError("Parent item not found")

    filename = _safe_filename(payload.title or "snapshot", "text/html") + ".html"
    storage_path = storage.save_attachment(
        item, filename, "text/html", payload.snapshotContent.encode("utf-8")
    )

    attachment = Attachment(
        item_id=item.id,
        filename=storage_path.split("/")[-1],
        content_type="text/html",
        size=len(payload.snapshotContent.encode("utf-8")),
        storage_path=storage_path,
    )
    db.add(attachment)
    db.flush()

    _save_session(session, db)
    return {}


def save_snapshot(db: Session, payload: ConnectorSaveSnapshotRequest) -> dict[str, Any]:
    """Create a parent item for a snapshot or direct PDF save."""
    session = get_or_create_session(db, payload.sessionID)

    item_type = "document" if payload.pdf else "webpage"
    item = Item(
        title=payload.title or payload.url or "Untitled",
        item_type=item_type,
        url=payload.url,
    )
    db.add(item)
    db.flush()

    item_map = dict(session.item_map)
    item_map[payload.sessionID] = str(item.id)
    session.item_map = item_map
    _save_session(session, db)
    return {}


def session_progress(db: Session, session_id: str) -> dict[str, Any]:
    """Return the current save progress for a connector session."""
    session = get_or_create_session(db, session_id)

    items: list[dict[str, Any]] = []
    for connector_id, anchor_id in session.item_map.items():
        item = db.get(Item, uuid.UUID(anchor_id))
        if item is None:
            continue
        items.append(
            {
                "id": connector_id,
                "title": item.title,
                "attachments": [
                    {"id": att_id, "title": "Attachment"}
                    for att_id in session.attachment_map
                ],
            }
        )

    return {"items": items, "done": len(session.pending_attachments) == 0}


def _safe_filename(title: str, content_type: str | None) -> str:
    """Build a reasonable filename from attachment metadata."""
    suffix = ".pdf" if content_type == "application/pdf" else ".epub"
    if content_type == "text/html":
        suffix = ".html"
    if not title.endswith((".pdf", ".epub", ".html")):
        return f"{title}{suffix}"
    return title
