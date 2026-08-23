"""Sync endpoints, mounted only on the central server (docs/sync.md)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from anchor_server.config import settings
from anchor_server.database import get_db
from anchor_server.schemas.sync import (
    ChangesResponse,
    PushRequest,
    PushResponse,
    SnapshotResponse,
    SyncStatusOut,
)
from anchor_server.services import sync_service

router = APIRouter(prefix="/sync", tags=["sync"])


def require_central_role() -> None:
    """Only a central-role server may serve the sync protocol."""
    if settings.role != "central":
        raise HTTPException(status_code=404, detail="Not found")


@router.post(
    "/push", response_model=PushResponse, dependencies=[Depends(require_central_role)]
)
def push(payload: PushRequest, db: Session = Depends(get_db)) -> PushResponse:
    """Apply a batch of device changes and append them to the oplog."""
    latest = sync_service.push_changes(db, payload.device_id, payload.changes)
    return PushResponse(applied=len(payload.changes), latest_seq=latest)


@router.get(
    "/changes",
    response_model=ChangesResponse,
    dependencies=[Depends(require_central_role)],
)
def changes(
    since: int = Query(0, ge=0), db: Session = Depends(get_db)
) -> ChangesResponse:
    """Return oplog entries newer than the device cursor.

    Responds 410 when the cursor fell behind retained history; the device
    must then re-bootstrap from a snapshot.
    """
    try:
        entries, latest = sync_service.changes_since(db, since)
    except sync_service.OplogGapError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    return ChangesResponse(
        changes=[
            {
                "seq": e.seq,
                "object_type": e.object_type,
                "object_id": e.object_id,
                "op": e.op,
                "payload": e.payload,
                "origin_device": e.origin_device,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        latest_seq=latest,
    )


@router.get(
    "/snapshot",
    response_model=SnapshotResponse,
    dependencies=[Depends(require_central_role)],
)
def get_snapshot(db: Session = Depends(get_db)) -> SnapshotResponse:
    """Full library dump for bootstrapping a new or stale device."""
    return sync_service.snapshot(db)


@router.get("/status", response_model=SyncStatusOut)
def status(db: Session = Depends(get_db)) -> SyncStatusOut:
    """Local sync state for the UI; available on any role."""
    from anchor_server.models import OutboxEntry, SyncState

    out = SyncStatusOut(role=settings.role, central_url=settings.central_url)
    state = db.get(SyncState, 1)
    if state is not None:
        out.device_id = state.device_id
        out.last_seq = state.last_seq
        out.last_sync_at = state.last_sync_at
    out.outbox_pending = db.query(OutboxEntry).count()
    return out
