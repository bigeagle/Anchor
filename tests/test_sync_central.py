"""Tests for the central sync endpoints (push / changes / snapshot)."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from anchor_server.config import settings
from anchor_server.models import Attachment, Item


@pytest.fixture
def central(client: TestClient, monkeypatch):
    """Run the app in central role."""
    monkeypatch.setattr(settings, "role", "central")
    return client


def _item_payload(item_id: uuid.UUID, **overrides) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": str(item_id),
        "title": "Synced Paper",
        "item_type": "journalArticle",
        "authors": [],
        "abstract": None,
        "publication": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "year": 2024,
        "doi": None,
        "arxiv_id": None,
        "isbn": None,
        "url": None,
        "language": None,
        "extra": {},
        "date_added": now,
        "date_modified": now,
        "version": 1,
        "deleted_at": None,
    }
    payload.update(overrides)
    return payload


def _push(client, changes, device_id="device-a"):
    return client.post(
        "/api/v1/sync/push", json={"device_id": device_id, "changes": changes}
    )


def test_sync_endpoints_require_central_role(client: TestClient):
    """On non-central roles the sync namespace does not exist."""
    response = client.get("/api/v1/sync/changes")
    assert response.status_code == 404


def test_push_upsert_creates_item(central: TestClient, db_session):
    """Pushing an upsert inserts the item and appends an oplog entry."""
    item_id = uuid.uuid4()
    response = _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(item_id),
                "op": "upsert",
                "payload": _item_payload(item_id),
            }
        ],
    )
    assert response.status_code == 200
    assert response.json() == {"applied": 1, "latest_seq": 1}

    item = db_session.get(Item, item_id)
    assert item is not None
    assert item.title == "Synced Paper"
    assert item.version == 1


def test_push_lww_overwrite(central: TestClient, db_session):
    """A later push for the same object overwrites the earlier one."""
    item_id = uuid.uuid4()
    _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(item_id),
                "op": "upsert",
                "payload": _item_payload(item_id, title="First"),
            }
        ],
    )
    _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(item_id),
                "op": "upsert",
                "payload": _item_payload(item_id, title="Second", version=2),
            }
        ],
        device_id="device-b",
    )

    item = db_session.get(Item, item_id)
    assert item.title == "Second"
    assert item.version == 2


def test_push_delete_sets_tombstone(central: TestClient, db_session):
    """A delete change stores the payload's deleted_at on the row."""
    item_id = uuid.uuid4()
    _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(item_id),
                "op": "upsert",
                "payload": _item_payload(item_id),
            }
        ],
    )
    deleted_at = datetime.now(timezone.utc).isoformat()
    _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(item_id),
                "op": "delete",
                "payload": _item_payload(item_id, version=2, deleted_at=deleted_at),
            }
        ],
    )

    item = db_session.get(Item, item_id)
    assert item.deleted_at is not None
    assert item.version == 2
    # Tombstoned rows stay invisible to the normal API.
    assert central.get(f"/api/v1/items/{item_id}").status_code == 404


def test_changes_incremental_pull(central: TestClient):
    """GET /changes returns only entries newer than the cursor, in order."""
    for _ in range(3):
        _push(
            central,
            [
                {
                    "object_type": "item",
                    "object_id": str(uuid.uuid4()),
                    "op": "upsert",
                    "payload": _item_payload(uuid.uuid4()),
                }
            ],
        )

    first = central.get("/api/v1/sync/changes?since=0").json()
    assert [c["seq"] for c in first["changes"]] == [1, 2, 3]
    assert first["latest_seq"] == 3
    assert first["changes"][0]["origin_device"] == "device-a"

    second = central.get("/api/v1/sync/changes?since=2").json()
    assert [c["seq"] for c in second["changes"]] == [3]


def test_changes_gap_returns_410(central: TestClient, db_session):
    """A cursor pointing into trimmed history yields 410."""
    from anchor_server.models import ChangeEntry

    # Simulate retention: only seq >= 5 survives.
    for seq in range(5, 8):
        db_session.add(
            ChangeEntry(
                seq=seq,
                object_type="item",
                object_id=uuid.uuid4(),
                op="upsert",
                payload={},
                origin_device="device-a",
            )
        )
    db_session.commit()

    response = central.get("/api/v1/sync/changes?since=2")
    assert response.status_code == 410

    # A cursor inside retained history still works.
    response = central.get("/api/v1/sync/changes?since=5")
    assert response.status_code == 200
    assert [c["seq"] for c in response.json()["changes"]] == [6, 7]


def test_snapshot_bootstrap(central: TestClient, db_session):
    """Snapshot returns live rows only, plus the oplog head as cursor."""
    live_id = uuid.uuid4()
    dead_id = uuid.uuid4()
    _push(
        central,
        [
            {
                "object_type": "item",
                "object_id": str(live_id),
                "op": "upsert",
                "payload": _item_payload(live_id, title="Live"),
            },
            {
                "object_type": "item",
                "object_id": str(dead_id),
                "op": "upsert",
                "payload": _item_payload(
                    dead_id,
                    title="Dead",
                    deleted_at=datetime.now(timezone.utc).isoformat(),
                ),
            },
        ],
    )
    db_session.add(
        Attachment(
            item_id=live_id,
            filename="paper.pdf",
            size=10,
            storage_path="pdfs/paper.pdf",
        )
    )
    db_session.commit()

    data = central.get("/api/v1/sync/snapshot").json()
    assert data["seq"] == 2
    assert [i["title"] for i in data["items"]] == ["Live"]
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["storage_path"] == "pdfs/paper.pdf"
