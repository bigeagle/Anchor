"""Tests for attachment endpoints."""

import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def item_id(client: TestClient):
    """Create an item and return its id."""
    payload = {"title": "Paper With Attachments", "item_type": "journalArticle"}
    response = client.post("/items/", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_attachment(client: TestClient, item_id):
    """POST /items/{id}/attachments should store the file."""
    response = client.post(
        f"/items/{item_id}/attachments",
        files={"file": ("hello.txt", BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "hello.txt"
    assert data["content_type"] == "text/plain"
    assert data["size"] == 11
    assert data["item_id"] == item_id


def test_list_attachments(client: TestClient, item_id):
    """GET /items/{id}/attachments should list uploaded files."""
    client.post(
        f"/items/{item_id}/attachments",
        files={"file": ("a.txt", BytesIO(b"a"), "text/plain")},
    )

    response = client.get(f"/items/{item_id}/attachments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "a.txt"


def test_download_attachment(client: TestClient, item_id):
    """GET /attachments/{id} should return the file content."""
    created = client.post(
        f"/items/{item_id}/attachments",
        files={"file": ("report.pdf", BytesIO(b"pdf data"), "application/pdf")},
    ).json()
    attachment_id = created["id"]

    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 200
    assert response.content == b"pdf data"
    assert response.headers["content-disposition"].endswith('filename="report.pdf"')


def test_delete_attachment(client: TestClient, item_id):
    """DELETE /attachments/{id} should remove the attachment."""
    created = client.post(
        f"/items/{item_id}/attachments",
        files={"file": ("temp.txt", BytesIO(b"temp"), "text/plain")},
    ).json()
    attachment_id = created["id"]

    response = client.delete(f"/attachments/{attachment_id}")
    assert response.status_code == 204

    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 404


def test_delete_item_cascades_attachments(client: TestClient, item_id):
    """Deleting an item should delete its attachments too."""
    created = client.post(
        f"/items/{item_id}/attachments",
        files={"file": ("cascade.txt", BytesIO(b"data"), "text/plain")},
    ).json()
    attachment_id = created["id"]

    response = client.delete(f"/items/{item_id}")
    assert response.status_code == 204

    response = client.get(f"/attachments/{attachment_id}")
    assert response.status_code == 404


def test_upload_to_unknown_item(client: TestClient):
    """Uploading to a non-existent item should return 404."""
    response = client.post(
        f"/items/{uuid.uuid4()}/attachments",
        files={"file": ("orphan.txt", BytesIO(b"x"), "text/plain")},
    )
    assert response.status_code == 404
