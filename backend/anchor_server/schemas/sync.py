"""Request/response schemas for the multi-device sync protocol (docs/sync.md)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

# Bump on any incompatible change to the sync protocol or synced schema.
# 1 = initial oplog protocol; 2 = chained checksums + 409/410 semantics.
SYNC_PROTOCOL_VERSION = 2

# Header devices send on every sync request; the central rejects mismatches.
SYNC_PROTOCOL_HEADER = "X-Anchor-Sync-Protocol"

ObjectType = Literal["item", "attachment"]
Op = Literal["upsert", "delete"]


class ChangeIn(BaseModel):
    """One local change pushed by a device."""

    object_type: ObjectType
    object_id: uuid.UUID
    op: Op
    payload: dict[str, Any]  # full row snapshot, incl. version/deleted_at


class PushRequest(BaseModel):
    """Batch of local changes a device pushes to the central server."""

    device_id: str
    changes: list[ChangeIn]


class PushResponse(BaseModel):
    """How many changes were applied and the resulting oplog head."""

    applied: int
    latest_seq: int


class ChangeOut(ChangeIn):
    """One oplog entry as returned to pulling devices."""

    seq: int
    origin_device: str
    checksum: str
    created_at: datetime


class ChangesResponse(BaseModel):
    """Oplog entries newer than the device's cursor."""

    changes: list[ChangeOut]
    latest_seq: int


class SnapshotResponse(BaseModel):
    """Full library dump for bootstrapping a device.

    ``seq`` and ``checksum`` identify the oplog head the snapshot is
    consistent with; the device adopts them as its initial cursor.
    """

    seq: int
    checksum: str
    items: list[dict[str, Any]]
    attachments: list[dict[str, Any]]


class SyncStatusOut(BaseModel):
    """Local sync state for the UI (available on any role)."""

    role: str
    protocol_version: int = SYNC_PROTOCOL_VERSION
    device_id: str | None = None
    last_seq: int | None = None
    last_sync_at: datetime | None = None
    outbox_pending: int = 0
    central_url: str | None = None
    sync_error: str | None = None
