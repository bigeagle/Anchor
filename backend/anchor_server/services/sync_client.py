"""Device-side sync client: outbox recording and the push/pull loop.

Local writes on a device are recorded into the `outbox` table via SQLAlchemy
event listeners, so every write path (public API, Zotero Connector, future
callers) is captured uniformly. A background loop pushes the outbox to the
central server and pulls oplog changes; see docs/sync.md.
"""

import asyncio
import contextvars
import logging
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import event
from sqlalchemy.orm import Session

from anchor_server.config import settings
from anchor_server.database import get_db_context
from anchor_server.models import (
    Attachment,
    Item,
    OutboxEntry,
    SyncState,
    utc_now,
)
from anchor_server.schemas import sync as sync_schemas
from anchor_server.schemas.sync import ChangeIn
from anchor_server.services.sync_service import apply_change, row_to_dict

logger = logging.getLogger(__name__)

# Set while applying pulled changes so they are not re-recorded into the
# outbox (which would echo them back to the central server forever).
_applying_remote: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "applying_remote", default=False
)

_TYPE_NAMES = {Item: "item", Attachment: "attachment"}


def _record_outbox(mapper, connection, target) -> None:
    """Append an outbox entry for a local insert/update (same transaction)."""
    if settings.role != "device" or _applying_remote.get():
        return
    object_type = _TYPE_NAMES.get(mapper.class_)
    if object_type is None:
        return
    op = "delete" if getattr(target, "deleted_at", None) is not None else "upsert"
    connection.execute(
        OutboxEntry.__table__.insert().values(
            object_type=object_type,
            object_id=target.id,
            op=op,
            payload=row_to_dict(target),
            created_at=utc_now(),
        )
    )


for _model in (Item, Attachment):
    event.listen(_model, "after_insert", _record_outbox)
    event.listen(_model, "after_update", _record_outbox)


def get_sync_state(db: Session) -> SyncState:
    """Return the single sync_state row, creating it (with device id) once.

    Creating the row means this machine just became a device: any library
    data from its standalone days is backfilled into the outbox so the first
    sync uploads it to the central server.
    """
    state = db.get(SyncState, 1)
    if state is None:
        state = SyncState(id=1, device_id=str(uuid.uuid4()), last_seq=0)
        db.add(state)
        _backfill_outbox(db)
        db.commit()
    return state


def _backfill_outbox(db: Session) -> None:
    """Enqueue all pre-existing live rows for a one-time upload.

    Rows already pending in the outbox are skipped so the first sync does
    not push duplicates.
    """
    pending = {(e.object_type, e.object_id) for e in db.query(OutboxEntry).all()}
    for object_type, model in (("item", Item), ("attachment", Attachment)):
        for obj in db.query(model).filter(model.deleted_at.is_(None)).all():
            if (object_type, obj.id) in pending:
                continue
            db.add(
                OutboxEntry(
                    object_type=object_type,
                    object_id=obj.id,
                    op="upsert",
                    payload=row_to_dict(obj),
                )
            )


def make_http() -> httpx.Client:
    """Build the HTTP client used to talk to the central server."""
    if not settings.central_url:
        raise RuntimeError("ANCHOR_CENTRAL_URL is required for device role")
    headers = {
        sync_schemas.SYNC_PROTOCOL_HEADER: str(sync_schemas.SYNC_PROTOCOL_VERSION)
    }
    if settings.sync_token:
        headers["Authorization"] = f"Bearer {settings.sync_token}"
    return httpx.Client(
        base_url=settings.central_url.rstrip("/"), headers=headers, timeout=30
    )


def _verify_central(http: httpx.Client) -> str | None:
    """Pre-flight the central before any sync traffic.

    Returns a halt code ("protocol_mismatch" / "not_a_central") or None when
    compatible. Network errors propagate — they are transient and the loop
    retries them.
    """
    response = http.get("/api/v1/sync/status")
    response.raise_for_status()
    data = response.json()
    if data.get("role") != "central":
        return "not_a_central"
    if data.get("protocol_version") != sync_schemas.SYNC_PROTOCOL_VERSION:
        return "protocol_mismatch"
    return None


def _halt(db: Session, error: str, message: str) -> None:
    """Stop syncing after a fatal central-side condition.

    ``cursor_mismatch`` halts are permanent until manual re-anchoring (delete
    the sync_state row and restart). ``protocol_mismatch`` halts are
    re-checked against the central on every sync attempt and clear themselves
    once both sides run the same protocol version again — upgrade skew is
    transient by nature (see ``_preflight``).
    """
    state = get_sync_state(db)
    if state.last_error == error:
        return
    state.last_error = error
    db.commit()
    hint = (
        "syncing resumes automatically once both sides run the same protocol version"
        if error == "protocol_mismatch"
        else "fix the deployment, then delete the sync_state row and restart "
        "to re-anchor this device"
    )
    logger.error("%s Syncing is halted; %s.", message, hint)


def _sticky_halted(db: Session) -> bool:
    """True when halted in a way that requires manual re-anchoring.

    ``cursor_mismatch`` (and ``not_a_central``) stay until the deployment is
    fixed and the device re-anchored: stop the server, delete the sync_state
    row (and any outbox rows), restart. ``protocol_mismatch`` is excluded —
    it recovers through ``_preflight`` once versions converge.
    """
    state = db.get(SyncState, 1)
    return (
        state is not None
        and state.last_error is not None
        and state.last_error != "protocol_mismatch"
    )


def _preflight(db: Session, http: httpx.Client) -> bool:
    """Pre-flight the central and manage protocol_mismatch halt state.

    Returns True when syncing cannot proceed: a mismatch (re)halts the
    device; a match after a protocol_mismatch halt clears the error and
    resumes — upgrade skew is transient by nature.
    """
    error = _verify_central(http)
    if error is not None:
        _halt(db, error, f"central pre-flight failed ({error}).")
        return True
    state = get_sync_state(db)
    if state.last_error == "protocol_mismatch":
        state.last_error = None
        db.commit()
        logger.info("central protocol version matches again; sync resumed")
    return False


def push_pending(db: Session, http: httpx.Client) -> int:
    """Push all pending outbox entries; delete them once acknowledged."""
    if _sticky_halted(db):
        return 0
    state = get_sync_state(db)  # first call backfills the standalone library
    entries = db.query(OutboxEntry).order_by(OutboxEntry.id).all()
    if not entries:
        return 0
    if _preflight(db, http):
        return 0
    body = {
        "device_id": state.device_id,
        "changes": [
            {
                "object_type": e.object_type,
                "object_id": str(e.object_id),
                "op": e.op,
                "payload": e.payload,
            }
            for e in entries
        ],
    }
    response = http.post("/api/v1/sync/push", json=body)
    if response.status_code == 426:
        _halt(db, "protocol_mismatch", "central rejected our protocol version.")
        return 0
    response.raise_for_status()
    for entry in entries:
        db.delete(entry)
    db.commit()
    return len(entries)


def _apply_entries(db: Session, changes: list[dict]) -> None:
    for change in changes:
        apply_change(db, ChangeIn(**change))
        logger.debug(
            "applied %s %s (%s)",
            change["op"],
            change["object_type"],
            change["object_id"],
        )


def pull_changes(db: Session, http: httpx.Client) -> int:
    """Pull oplog entries newer than the cursor and apply them.

    The cursor advances in the same transaction as the applied changes, so a
    crash mid-apply simply re-fetches the same entries (apply is idempotent).
    A 410 means the cursor fell behind retained history: re-bootstrap.
    A 409 means the oplog chain does not match (wrong central or rolled-back
    oplog): halts until manual re-anchoring — auto-bootstrapping here could
    wipe the local library if the new central is empty. A 426 means a
    protocol version mismatch: halts too, but recovers automatically once
    both sides run the same protocol version again.
    """
    if _sticky_halted(db):
        return 0
    if _preflight(db, http):
        return -2
    state = get_sync_state(db)
    if state.last_seq and state.last_checksum is None:
        # Legacy cursor from before checksums existed: cannot be verified,
        # so re-bootstrap once to adopt a verifiable (seq, checksum) pair.
        bootstrap(db, http)
        return -1
    params: dict[str, Any] = {"since": state.last_seq}
    if state.last_checksum:
        params["checksum"] = state.last_checksum
    response = http.get("/api/v1/sync/changes", params=params)
    if response.status_code == 409:
        _halt(
            db,
            "cursor_mismatch",
            f"central rejected the sync cursor (seq={state.last_seq}): "
            f"{response.json().get('detail', response.text)}.",
        )
        return -2
    if response.status_code == 426:
        _halt(db, "protocol_mismatch", "central rejected our protocol version.")
        return -2
    if response.status_code == 410:
        logger.warning(
            "cursor %d fell behind retained oplog history; re-bootstrapping",
            state.last_seq,
        )
        bootstrap(db, http)
        return -1
    response.raise_for_status()
    data = response.json()

    token = _applying_remote.set(True)
    try:
        _apply_entries(db, data["changes"])
        previous = state.last_seq
        state.last_seq = data["latest_seq"]
        if data["changes"]:
            state.last_checksum = data["changes"][-1]["checksum"]
        state.last_sync_at = utc_now()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        _applying_remote.reset(token)
    if data["changes"]:
        logger.info(
            "pulled %d change(s) from central (cursor %d -> %d)",
            len(data["changes"]),
            previous,
            state.last_seq,
        )
    return len(data["changes"])


def bootstrap(db: Session, http: httpx.Client) -> None:
    """Replace local library state with a central snapshot.

    Local rows missing from the snapshot are tombstoned — they were deleted
    on other devices while this one was stale. Unpushed local changes are
    safe because sync_once always pushes before pulling/bootstrapping.
    """
    response = http.get("/api/v1/sync/snapshot")
    response.raise_for_status()
    data = response.json()

    token = _applying_remote.set(True)
    try:
        seen: dict[str, set[uuid.UUID]] = {"item": set(), "attachment": set()}
        for object_type, payloads in (
            ("item", data["items"]),
            ("attachment", data["attachments"]),
        ):
            for payload in payloads:
                object_id = uuid.UUID(payload["id"])
                apply_change(
                    db,
                    ChangeIn(
                        object_type=object_type,
                        object_id=object_id,
                        op="upsert",
                        payload=payload,
                    ),
                )
                seen[object_type].add(object_id)

        now = utc_now()
        for model, object_type in ((Item, "item"), (Attachment, "attachment")):
            for obj in db.query(model).filter(model.deleted_at.is_(None)):
                if obj.id not in seen[object_type]:
                    obj.deleted_at = now
                    obj.version += 1

        state = get_sync_state(db)
        state.last_seq = data["seq"]
        state.last_checksum = data["checksum"]
        state.last_sync_at = now
        state.last_error = None
        db.commit()
        logger.info(
            "bootstrapped from snapshot: %d item(s), %d attachment(s), cursor -> %d",
            len(data["items"]),
            len(data["attachments"]),
            data["seq"],
        )
    except Exception:
        db.rollback()
        raise
    finally:
        _applying_remote.reset(token)


def sync_once(db: Session, http: httpx.Client) -> None:
    """One full sync round: push local changes, then pull remote ones."""
    push_pending(db, http)
    pull_changes(db, http)


async def sync_loop() -> None:
    """Background task: push promptly on local writes, poll on the interval."""
    http = make_http()
    logger.info(
        "sync loop started: central=%s, pull interval=%ds",
        settings.central_url,
        settings.sync_interval,
    )
    last_pull = 0.0
    while True:
        try:
            pushed, pulled = await asyncio.to_thread(_sync_tick, http, last_pull)
            if pulled:
                last_pull = time.monotonic()
            if pushed:
                logger.info("pushed %d change(s) to central", pushed)
        except Exception:
            logger.exception("sync iteration failed; will retry")
        await asyncio.sleep(5)


def _sync_tick(http: httpx.Client, last_pull: float) -> tuple[int, bool]:
    """Push pending changes; pull when the configured interval elapsed."""
    with get_db_context() as db:
        pushed = push_pending(db, http)
    if time.monotonic() - last_pull >= settings.sync_interval:
        with get_db_context() as db:
            pull_changes(db, http)
        return pushed, True
    return pushed, False
