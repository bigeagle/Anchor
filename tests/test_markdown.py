"""Tests for attachment Markdown conversion endpoint."""

import uuid

import pytest
from fastapi.testclient import TestClient

from anchor_server.models import Attachment, Item
from anchor_server.services import markdown_service, storage


@pytest.fixture
def text_attachment(db_session, temp_data_dir):
    """Create an item with a text-file attachment."""
    item = Item(title="Test Item", item_type="document")
    db_session.add(item)
    db_session.flush()

    data = b"Hello, Markdown!\n"
    relative_path = storage.save_attachment(item, "sample.txt", "text/plain", data)

    attachment = Attachment(
        item_id=item.id,
        filename="sample.txt",
        content_type="text/plain",
        size=len(data),
        storage_path=relative_path,
    )
    db_session.add(attachment)
    db_session.commit()
    db_session.refresh(attachment)
    return attachment


def test_get_attachment_markdown_converts_and_caches(
    client: TestClient, text_attachment, temp_data_dir
):
    """GET /attachments/{id}/markdown should convert and cache the result."""
    response = client.get(f"/api/v1/attachments/{text_attachment.id}/markdown")
    assert response.status_code == 200
    assert "Hello, Markdown!" in response.text

    cache_path = markdown_service._cache_path(str(text_attachment.id))
    assert cache_path.exists()
    assert cache_path.read_text(encoding="utf-8") == response.text


def test_get_attachment_markdown_uses_cache(client: TestClient, text_attachment):
    """The endpoint should return cached Markdown if it is still valid."""
    # First call populates the cache.
    first = client.get(f"/api/v1/attachments/{text_attachment.id}/markdown").text

    # Overwrite the source file; if the cache is used, we still see the old text.
    sample_path = storage.settings.attachments_dir / text_attachment.storage_path
    sample_path.write_text("Updated text\n", encoding="utf-8")
    second = client.get(f"/api/v1/attachments/{text_attachment.id}/markdown").text
    assert first == second
    assert "Hello, Markdown!" in second


def test_delete_attachment_invalidates_cache(
    client: TestClient, text_attachment, temp_data_dir, db_session
):
    """Deleting an attachment should remove its Markdown cache."""
    client.get(f"/api/v1/attachments/{text_attachment.id}/markdown")
    cache_path = markdown_service._cache_path(str(text_attachment.id))
    assert cache_path.exists()

    client.delete(f"/api/v1/attachments/{text_attachment.id}")
    assert not cache_path.exists()


def test_get_attachment_markdown_not_found(client: TestClient):
    """GET /attachments/{id}/markdown should 404 for unknown attachments."""
    response = client.get(f"/api/v1/attachments/{uuid.uuid4()}/markdown")
    assert response.status_code == 404
