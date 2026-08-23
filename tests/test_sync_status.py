"""Tests for the sync status endpoint."""

import uuid

from fastapi.testclient import TestClient

from anchor_server.models import OutboxEntry, SyncState


def test_status_standalone(client: TestClient):
    """Standalone role reports no device state and an empty outbox."""
    data = client.get("/api/v1/sync/status").json()
    assert data["role"] == "standalone"
    assert data["device_id"] is None
    assert data["outbox_pending"] == 0


def test_status_device(client: TestClient, db_session, monkeypatch):
    """Device role exposes device id, cursor, and pending outbox count."""
    from anchor_server.config import settings

    monkeypatch.setattr(settings, "role", "device")
    db_session.add(SyncState(id=1, device_id="dev-1", last_seq=42))
    db_session.commit()

    # A pending local change.
    client.post("/api/v1/items/", json={"title": "Pending"})

    data = client.get("/api/v1/sync/status").json()
    assert data["role"] == "device"
    assert data["device_id"] == "dev-1"
    assert data["last_seq"] == 42
    assert data["outbox_pending"] == 1


def test_status_available_on_central(client: TestClient, db_session, monkeypatch):
    """The status endpoint is not gated behind the central role."""
    from anchor_server.config import settings

    monkeypatch.setattr(settings, "role", "central")
    db_session.add(
        OutboxEntry(object_type="item", object_id=uuid.uuid4(), op="upsert", payload={})
    )
    db_session.commit()
    response = client.get("/api/v1/sync/status")
    assert response.status_code == 200
    assert response.json()["role"] == "central"
