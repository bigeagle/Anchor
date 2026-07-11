"""Tests for attachment endpoints."""

import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def item_id(client: TestClient):
    """Create an item and return its id."""
    payload = {
        "title": "Paper With Attachments",
        "item_type": "journalArticle",
        "year": 2024,
        "authors": [{"firstName": "Alice", "lastName": "Smith"}],
    }
    response = client.post("/api/v1/items/", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_attachment(client: TestClient, item_id):
    """POST /items/{id}/attachments should store and rename the file."""
    response = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("hello.txt", BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "2024_smith_paper_with_attachments.txt"
    assert data["content_type"] == "text/plain"
    assert data["size"] == 11
    assert data["item_id"] == item_id


def test_list_attachments(client: TestClient, item_id):
    """GET /items/{id}/attachments should list uploaded files."""
    client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("a.txt", BytesIO(b"a"), "text/plain")},
    )

    response = client.get(f"/api/v1/items/{item_id}/attachments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "2024_smith_paper_with_attachments.txt"


def test_download_attachment(client: TestClient, item_id):
    """GET /attachments/{id} should return the file content."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("report.pdf", BytesIO(b"pdf data"), "application/pdf")},
    ).json()
    attachment_id = created["id"]

    response = client.get(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 200
    assert response.content == b"pdf data"
    assert response.headers["content-disposition"] == "inline"


def test_download_html_inline(client: TestClient, item_id):
    """HTML attachments should be served inline for browser preview."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("page.html", BytesIO(b"<html></html>"), "text/html")},
    ).json()
    attachment_id = created["id"]

    response = client.get(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == "inline"


def test_download_binary_attachment(client: TestClient, item_id):
    """Unknown binary types should still be offered as downloads."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("data.bin", BytesIO(b"binary"), "application/octet-stream")},
    ).json()
    attachment_id = created["id"]

    response = client.get(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith(
        'filename="2024_smith_paper_with_attachments.bin"'
    )


def test_delete_attachment(client: TestClient, item_id):
    """DELETE /attachments/{id} should remove the attachment."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("temp.txt", BytesIO(b"temp"), "text/plain")},
    ).json()
    attachment_id = created["id"]

    response = client.delete(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 404


def test_delete_item_cascades_attachments(client: TestClient, item_id):
    """Deleting an item should delete its attachments too."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("cascade.txt", BytesIO(b"data"), "text/plain")},
    ).json()
    attachment_id = created["id"]

    response = client.delete(f"/api/v1/items/{item_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 404


def test_upload_to_unknown_item(client: TestClient):
    """Uploading to a non-existent item should return 404."""
    response = client.post(
        f"/api/v1/items/{uuid.uuid4()}/attachments",
        files={"file": ("orphan.txt", BytesIO(b"x"), "text/plain")},
    )
    assert response.status_code == 404


def test_pdf_and_others_separated(client: TestClient, item_id):
    """PDFs and non-PDFs should be stored in separate directories."""
    pdf = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("report.pdf", BytesIO(b"pdf"), "application/pdf")},
    ).json()
    other = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("notes.txt", BytesIO(b"txt"), "text/plain")},
    ).json()

    assert pdf["storage_path"].startswith("pdfs/")
    assert other["storage_path"].startswith("others/")


def test_duplicate_attachment_name_protected(client: TestClient, item_id):
    """Uploading the same conceptual attachment twice should append a counter."""
    first = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("same.pdf", BytesIO(b"first"), "application/pdf")},
    ).json()
    second = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("same.pdf", BytesIO(b"second"), "application/pdf")},
    ).json()

    assert first["filename"] == "2024_smith_paper_with_attachments.pdf"
    assert second["filename"] == "2024_smith_paper_with_attachments_1.pdf"


def test_template_subdirectories_are_created(client: TestClient, item_id, monkeypatch):
    """Template output containing path separators should create subdirectories."""
    from anchor_server.config import settings

    monkeypatch.setattr(
        settings,
        "attachment_name_template",
        "{{ year }}/{{ authors_last_names }}/{{ title_slug }}",
    )

    response = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("report.pdf", BytesIO(b"pdf"), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["storage_path"].startswith("pdfs/2024/smith/paper_with_attachments.pdf")
