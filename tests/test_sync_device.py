"""Tests for the device-side sync client: outbox, push/pull, bootstrap."""

import asyncio
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from anchor_server.config import settings
from anchor_server.database import Base, get_db
from anchor_server.main import app
from anchor_server.models import Attachment, ChangeEntry, Item, OutboxEntry, SyncState
from anchor_server.services import sync_client
from anchor_server.services.sync_service import row_to_dict


class CentralHarness:
    """Run the same app as a central server with its own in-memory database.

    Swaps the get_db override and the role setting for the duration of each
    central call, so the device under test and the central server can share
    one process in tests.
    """

    def __init__(self, central_session):
        self.central_session = central_session
        self._http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://central"
        )

    def as_central(self, call):
        previous_role = settings.role
        previous_override = app.dependency_overrides.get(get_db)
        settings.role = "central"

        def override():
            yield self.central_session

        app.dependency_overrides[get_db] = override
        try:
            return call()
        finally:
            settings.role = previous_role
            if previous_override is not None:
                app.dependency_overrides[get_db] = previous_override
            else:
                app.dependency_overrides.pop(get_db, None)

    def post(self, *args, **kwargs):
        return self.as_central(lambda: asyncio.run(self._http.post(*args, **kwargs)))

    def get(self, *args, **kwargs):
        return self.as_central(lambda: asyncio.run(self._http.get(*args, **kwargs)))


@pytest.fixture
def device(client: TestClient, monkeypatch):
    """Put the app-under-test into device role."""
    monkeypatch.setattr(settings, "role", "device")
    return client


@pytest.fixture
def central():
    """Provide a central harness backed by a fresh in-memory database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield CentralHarness(session)
    finally:
        session.close()


def test_outbox_records_local_writes(device: TestClient, db_session):
    """Create/update/delete on items and attachments all land in the outbox."""
    created = device.post("/api/v1/items/", json={"title": "Local Paper"}).json()
    entries = db_session.query(OutboxEntry).all()
    assert len(entries) == 1
    assert entries[0].object_type == "item"
    assert entries[0].op == "upsert"
    assert entries[0].payload["id"] == created["id"]
    assert entries[0].payload["title"] == "Local Paper"

    device.put(f"/api/v1/items/{created['id']}", json={"title": "Renamed"})
    device.delete(f"/api/v1/items/{created['id']}")

    entries = db_session.query(OutboxEntry).order_by(OutboxEntry.id).all()
    assert [e.op for e in entries] == ["upsert", "upsert", "delete"]
    assert entries[-1].payload["deleted_at"] is not None


def test_standalone_role_writes_no_outbox(client: TestClient, db_session):
    """Without device role, local writes do not touch the outbox."""
    client.post("/api/v1/items/", json={"title": "Offline Paper"})
    assert db_session.query(OutboxEntry).count() == 0


def test_sync_roundtrip(device: TestClient, db_session, central):
    """Push local changes to central, then pull a remote change back."""
    created = device.post("/api/v1/items/", json={"title": "From Device"}).json()
    item_id = uuid.UUID(created["id"])

    sync_client.sync_once(db_session, central)

    pushed = central.central_session.get(Item, item_id)
    assert pushed is not None
    assert pushed.title == "From Device"
    assert db_session.query(OutboxEntry).count() == 0
    assert sync_client.get_sync_state(db_session).last_seq == 1

    # Simulate another device editing the item on central.
    def remote_edit():
        session = central.central_session
        item = session.get(Item, item_id)
        item.title = "Edited Elsewhere"
        item.version += 1
        session.add(
            ChangeEntry(
                object_type="item",
                object_id=item.id,
                op="upsert",
                payload=row_to_dict(item),
                origin_device="device-b",
            )
        )
        session.commit()

    central.as_central(remote_edit)

    sync_client.sync_once(db_session, central)

    local = db_session.get(Item, item_id)
    assert local.title == "Edited Elsewhere"
    assert local.version == 2
    # The pulled change must not echo back into the outbox.
    assert db_session.query(OutboxEntry).count() == 0
    assert sync_client.get_sync_state(db_session).last_seq == 2


def test_pull_gap_bootstraps_from_snapshot(device: TestClient, db_session, central):
    """A 410 from /changes re-bootstraps the device from a snapshot."""
    # A local row created before this device ever synced (a "zombie").
    settings.role = "standalone"  # predates device mode: no outbox entry
    zombie = Item(title="Stale Local Only", item_type="book")
    db_session.add(zombie)
    # The device synced before (state row exists), so no backfill happens.
    db_session.add(SyncState(id=1, device_id="dev-stale", last_seq=2))
    db_session.commit()
    settings.role = "device"

    live_id = uuid.uuid4()

    def seed_central():
        session = central.central_session
        for seq in (5, 6):
            session.add(
                ChangeEntry(
                    seq=seq,
                    object_type="item",
                    object_id=uuid.uuid4(),
                    op="upsert",
                    payload={},
                    origin_device="device-x",
                )
            )
        session.add(Item(id=live_id, title="Snapshot Item", item_type="book"))
        session.commit()

    central.as_central(seed_central)

    assert sync_client.pull_changes(db_session, central) == -1

    db_session.expire_all()
    live = db_session.get(Item, live_id)
    assert live is not None and live.title == "Snapshot Item"
    assert db_session.get(Item, zombie.id).deleted_at is not None
    assert sync_client.get_sync_state(db_session).last_seq == 6
    # Nothing was recorded into the outbox while applying the snapshot.
    assert db_session.query(OutboxEntry).count() == 0


def test_first_sync_uploads_standalone_library(device: TestClient, db_session, central):
    """Data from the standalone era is backfilled and pushed on first sync."""
    # Library accumulated while running standalone: no outbox entries.
    settings.role = "standalone"
    created = device.post("/api/v1/items/", json={"title": "Old Standalone"}).json()
    device.post(
        f"/api/v1/items/{created['id']}/attachments",
        files={"file": ("old.pdf", b"pdf-bytes", "application/pdf")},
    )
    settings.role = "device"
    assert db_session.query(OutboxEntry).count() == 0

    # Becoming a device backfills everything; sync_once uploads it.
    sync_client.sync_once(db_session, central)

    assert db_session.query(OutboxEntry).count() == 0
    item = central.central_session.get(Item, uuid.UUID(created["id"]))
    assert item is not None and item.title == "Old Standalone"
    assert (
        central.central_session.query(Attachment).filter_by(item_id=item.id).count()
        == 1
    )
