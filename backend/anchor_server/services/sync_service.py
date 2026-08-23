"""Central-side sync logic: apply pushed changes, serve oplog and snapshots.

The oplog (`changes` table) is the authoritative ordering. Applying a change
means replacing the whole row with the pushed payload (LWW); deletes arrive
as payloads with ``deleted_at`` set, so upsert and delete share one path.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import Session
from sqlalchemy import Uuid

from anchor_server.models import Attachment, ChangeEntry, Item
from anchor_server.schemas.sync import ChangeIn, SnapshotResponse

MODELS: dict[str, type[Item] | type[Attachment]] = {
    "item": Item,
    "attachment": Attachment,
}


class OplogGapError(Exception):
    """Raised when a device's cursor fell behind retained oplog history."""


def _coerce(model: type, data: dict[str, Any]) -> dict[str, Any]:
    """Convert JSON-safe payload values back to Python types for the ORM."""
    columns = model.__table__.columns
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key not in columns:
            continue
        column = columns[key]
        if value is not None:
            if isinstance(column.type, Uuid):
                value = uuid.UUID(str(value))
            elif isinstance(column.type, DateTime):
                value = datetime.fromisoformat(str(value))
        out[key] = value
    return out


def row_to_dict(obj: Any) -> dict[str, Any]:
    """Serialize an ORM row to a JSON-safe dict (uuids and datetimes as str)."""
    out: dict[str, Any] = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        out[column.name] = value
    return out


def apply_change(db: Session, change: ChangeIn) -> None:
    """Apply one pushed change to the central tables (whole-row replace)."""
    model = MODELS[change.object_type]
    data = _coerce(model, change.payload)
    data["id"] = change.object_id
    obj = db.get(model, change.object_id)
    if obj is None:
        db.add(model(**data))
    else:
        for key, value in data.items():
            setattr(obj, key, value)


def push_changes(db: Session, device_id: str, changes: list[ChangeIn]) -> int:
    """Apply a batch of device changes and append them to the oplog.

    Returns the oplog head (highest seq) after the batch.
    """
    for change in changes:
        apply_change(db, change)
        db.add(
            ChangeEntry(
                object_type=change.object_type,
                object_id=change.object_id,
                op=change.op,
                payload=change.payload,
                origin_device=device_id,
            )
        )
    db.commit()
    return latest_seq(db)


def latest_seq(db: Session) -> int:
    """Return the current oplog head, or 0 when the oplog is empty."""
    return db.scalar(select(func.max(ChangeEntry.seq))) or 0


def changes_since(db: Session, since: int) -> tuple[list[ChangeEntry], int]:
    """Return oplog entries with seq > `since`, plus the oplog head.

    Raises OplogGapError if the cursor points into trimmed history; the
    caller translates that into a 410 so the device re-bootstraps.
    """
    oldest = db.scalar(select(func.min(ChangeEntry.seq)))
    if oldest is not None and since and since < oldest - 1:
        raise OplogGapError(f"cursor {since} is older than retained oplog")
    entries = (
        db.query(ChangeEntry)
        .filter(ChangeEntry.seq > since)
        .order_by(ChangeEntry.seq)
        .all()
    )
    return entries, latest_seq(db)


def snapshot(db: Session) -> SnapshotResponse:
    """Build a full-library snapshot plus the oplog head it is consistent with."""
    items = db.query(Item).filter(Item.deleted_at.is_(None)).all()
    attachments = db.query(Attachment).filter(Attachment.deleted_at.is_(None)).all()
    return SnapshotResponse(
        seq=latest_seq(db),
        items=[row_to_dict(item) for item in items],
        attachments=[row_to_dict(a) for a in attachments],
    )
