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


def test_delete_attachment_is_soft_delete(client: TestClient, db_session, item_id):
    """DELETE should leave a tombstone row and remove the file from disk."""
    from anchor_server.config import settings
    from anchor_server.models import Attachment

    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("soft.txt", BytesIO(b"soft"), "text/plain")},
    ).json()
    attachment_id = created["id"]

    response = client.delete(f"/api/v1/attachments/{attachment_id}")
    assert response.status_code == 204

    attachment = db_session.get(Attachment, uuid.UUID(attachment_id))
    assert attachment is not None
    assert attachment.deleted_at is not None
    assert attachment.version == created["version"] + 1
    assert not (settings.attachments_dir / created["storage_path"]).exists()

    # Hidden from the item's attachment list.
    assert client.get(f"/api/v1/items/{item_id}/attachments").json() == []
    # And from the item detail payload.
    assert client.get(f"/api/v1/items/{item_id}").json()["attachments"] == []


def test_attachment_availability_flags(client: TestClient, db_session, item_id):
    """Attachments report local availability and size mismatches."""
    from anchor_server.config import settings
    from anchor_server.models import Attachment

    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("avail.txt", BytesIO(b"12345"), "text/plain")},
    ).json()
    assert created["available"] is True
    assert created["size_mismatch"] is False

    # Metadata exists but the file has not arrived (e.g. Syncthing pending).
    ghost = Attachment(
        item_id=uuid.UUID(item_id),
        filename="ghost.pdf",
        content_type="application/pdf",
        size=100,
        storage_path="pdfs/ghost.pdf",
    )
    db_session.add(ghost)
    db_session.commit()

    attachments = client.get(f"/api/v1/items/{item_id}/attachments").json()
    by_name = {a["filename"]: a for a in attachments}
    assert by_name["ghost.pdf"]["available"] is False
    assert by_name["ghost.pdf"]["size_mismatch"] is False

    # A file exists but its size differs from the metadata.
    ghost_path = settings.attachments_dir / "pdfs/ghost.pdf"
    ghost_path.parent.mkdir(parents=True, exist_ok=True)
    ghost_path.write_bytes(b"x" * 50)
    attachments = client.get(f"/api/v1/items/{item_id}/attachments").json()
    by_name = {a["filename"]: a for a in attachments}
    assert by_name["ghost.pdf"]["available"] is True
    assert by_name["ghost.pdf"]["size_mismatch"] is True


def test_upload_duplicate_content_rejected(client: TestClient, item_id):
    """Re-saving the same item with identical content returns 409."""
    first = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("dup.pdf", BytesIO(b"same bytes"), "application/pdf")},
    )
    assert first.status_code == 201

    # Same item, same content: renders the same target path — a duplicate.
    response = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("dup.pdf", BytesIO(b"same bytes"), "application/pdf")},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["existing_item_id"] == item_id
    assert detail["existing_item_title"] == "Paper With Attachments"
    assert detail["existing_attachment_id"] == first.json()["id"]


def test_same_content_on_other_item_allowed(client: TestClient, item_id):
    """Dedup is keyed by the rendered path: a different item is not a dupe."""
    first = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("dup.pdf", BytesIO(b"same bytes"), "application/pdf")},
    )
    assert first.status_code == 201

    other = client.post(
        "/api/v1/items/",
        json={"title": "Other Paper", "item_type": "journalArticle"},
    ).json()
    response = client.post(
        f"/api/v1/items/{other['id']}/attachments",
        files={"file": ("dup2.pdf", BytesIO(b"same bytes"), "application/pdf")},
    )
    assert response.status_code == 201


def test_upload_adopts_orphan_file(client: TestClient, item_id):
    """An on-disk file with no live attachment should be reused, not suffixed."""
    from anchor_server.config import settings

    orphan = settings.attachments_dir / "pdfs/2024_smith_paper_with_attachments.pdf"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan content")

    response = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("whatever.pdf", BytesIO(b"orphan content"), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["storage_path"] == "pdfs/2024_smith_paper_with_attachments.pdf"
    assert data["filename"] == "2024_smith_paper_with_attachments.pdf"


def test_upload_same_name_different_content_suffixed(client: TestClient, item_id):
    """Different content colliding on the rendered name still gets a counter."""
    first = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("a.pdf", BytesIO(b"content a"), "application/pdf")},
    ).json()
    second = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("b.pdf", BytesIO(b"content b"), "application/pdf")},
    )
    assert second.status_code == 201
    assert first["filename"] == "2024_smith_paper_with_attachments.pdf"
    assert second.json()["filename"] == "2024_smith_paper_with_attachments_1.pdf"


def test_upload_after_delete_not_duplicate(client: TestClient, item_id):
    """Re-uploading content whose attachment was deleted should succeed."""
    created = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("gone.pdf", BytesIO(b"deleted bytes"), "application/pdf")},
    ).json()
    assert client.delete(f"/api/v1/attachments/{created['id']}").status_code == 204

    response = client.post(
        f"/api/v1/items/{item_id}/attachments",
        files={"file": ("gone.pdf", BytesIO(b"deleted bytes"), "application/pdf")},
    )
    assert response.status_code == 201
