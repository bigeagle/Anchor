"""Central-side sync logic: apply pushed changes, serve oplog and snapshots.

The oplog (`changes` table) is the authoritative ordering. Applying a change
means replacing the whole row with the pushed payload (LWW); deletes arrive
as payloads with ``deleted_at`` set, so upsert and delete share one path.

Each oplog entry carries a chained checksum: sha256 over the previous
entry's checksum (or the central's instance_id for the first entry) plus the
canonical JSON of the entry. Devices present their cursor as
(seq, checksum); the central verifies the chain before serving an increment,
so a device pointed at the wrong central (or a rolled-back oplog) is
rejected loudly instead of silently diverging.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Uuid, func, select
from sqlalchemy.orm import Session

from anchor_server.models import Attachment, ChangeEntry, Item, SyncMeta
from anchor_server.schemas.sync import ChangeIn, SnapshotResponse

MODELS: dict[str, type[Item] | type[Attachment]] = {
    "item": Item,
    "attachment": Attachment,
}


class OplogGapError(Exception):
    """Raised when a device's cursor fell behind retained oplog history."""


class CursorMismatchError(Exception):
    """Raised when a device's cursor does not match this oplog chain.

    Means the device synced against a different central, or this oplog was
    rolled back. Syncing must halt for manual re-anchoring, not silently
    continue or auto-bootstrap (which could wipe the device's library).
    """


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
        # With autoflush=False, Session.get misses unflushed pending
        # instances: a second change for the same object in one batch would
        # insert a duplicate row. Check session.new before adding.
        obj = next(
            (o for o in db.new if isinstance(o, model) and o.id == change.object_id),
            None,
        )
    if obj is None:
        db.add(model(**data))
    else:
        for key, value in data.items():
            setattr(obj, key, value)


def get_instance_id(db: Session) -> str:
    """Return the central's instance id, generating and storing it once."""
    meta = db.get(SyncMeta, 1)
    if meta is None:
        meta = SyncMeta(id=1, instance_id=str(uuid.uuid4()))
        db.add(meta)
        db.commit()
    return meta.instance_id


def compute_checksum(
    prev_checksum: str,
    object_type: str,
    object_id: uuid.UUID | str,
    op: str,
    payload: dict[str, Any],
) -> str:
    """Chain an oplog entry to its predecessor.

    The first entry chains from the central's instance_id, so two different
    centrals always produce different chains.
    """
    canonical = json.dumps(
        {
            "object_type": object_type,
            "object_id": str(object_id),
            "op": op,
            "payload": payload,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(f"{prev_checksum}|{canonical}".encode()).hexdigest()


def head(db: Session) -> tuple[int, str]:
    """Return the oplog head as (seq, checksum); (0, instance_id) when empty."""
    entry = db.query(ChangeEntry).order_by(ChangeEntry.seq.desc()).first()
    if entry is None:
        return 0, get_instance_id(db)
    return entry.seq, entry.checksum


def latest_seq(db: Session) -> int:
    """Return the current oplog head, or 0 when the oplog is empty."""
    return head(db)[0]


def push_changes(db: Session, device_id: str, changes: list[ChangeIn]) -> int:
    """Apply a batch of device changes and append them to the oplog.

    Returns the oplog head (highest seq) after the batch.
    """
    _, prev_checksum = head(db)
    for change in changes:
        apply_change(db, change)
        prev_checksum = compute_checksum(
            prev_checksum,
            change.object_type,
            change.object_id,
            change.op,
            change.payload,
        )
        db.add(
            ChangeEntry(
                object_type=change.object_type,
                object_id=change.object_id,
                op=change.op,
                payload=change.payload,
                origin_device=device_id,
                checksum=prev_checksum,
            )
        )
    db.commit()
    return latest_seq(db)


def changes_since(
    db: Session, since: int, checksum: str | None
) -> tuple[list[ChangeEntry], int]:
    """Return oplog entries with seq > `since`, plus the oplog head.

    When `checksum` is given, the entry at `since` must exist and match it:
    - missing and beyond the head -> the oplog rolled back or this is the
      wrong central -> CursorMismatchError (409, halt for manual re-anchor)
    - missing but inside the head -> trimmed history -> OplogGapError (410,
      auto re-bootstrap)
    - present but different -> different chain -> CursorMismatchError (409)
    """
    if since and checksum is not None:
        cursor_entry = db.get(ChangeEntry, since)
        if cursor_entry is None:
            if since > latest_seq(db):
                raise CursorMismatchError(
                    f"cursor seq {since} is beyond this oplog's head"
                )
            raise OplogGapError(f"cursor {since} is older than retained oplog")
        if cursor_entry.checksum != checksum:
            raise CursorMismatchError(f"cursor checksum mismatch at seq {since}")
    elif since:
        oldest = db.scalar(select(func.min(ChangeEntry.seq)))
        if oldest is not None and since < oldest - 1:
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
    seq, checksum = head(db)
    return SnapshotResponse(
        seq=seq,
        checksum=checksum,
        items=[row_to_dict(item) for item in items],
        attachments=[row_to_dict(a) for a in attachments],
    )
