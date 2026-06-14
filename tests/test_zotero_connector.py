"""Tests for Zotero Connector endpoints (Phase 2.1)."""

import json

import pytest
from fastapi.testclient import TestClient

from anchor_server.models import Attachment, ConnectorSession, Item
from anchor_server.services import storage


@pytest.fixture
def article_payload():
    """Return a minimal saveItems payload for a journal article."""
    return {
        "sessionID": "test-session-1",
        "uri": "https://example.com/article",
        "items": [
            {
                "id": "item1",
                "itemType": "journalArticle",
                "title": "Example Paper",
                "url": "https://example.com/article",
                "DOI": "10.1234/example",
                "date": "2024-03-15",
                "creators": [
                    {
                        "creatorType": "author",
                        "firstName": "Alice",
                        "lastName": "Smith",
                    }
                ],
                "attachments": [
                    {
                        "id": "att1",
                        "parentItem": "item1",
                        "title": "Full Text PDF",
                        "url": "https://example.com/article.pdf",
                        "mimeType": "application/pdf",
                    }
                ],
            }
        ],
    }


def test_ping_returns_capabilities(client: TestClient):
    """POST /connector/ping should advertise the modern upload workflow."""
    response = client.post("/connector/ping", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["prefs"]["supportsAttachmentUpload"] is True
    assert "X-Zotero-Version" in response.headers


def test_get_selected_collection(client: TestClient):
    """POST /connector/getSelectedCollection should return the default library."""
    response = client.post("/connector/getSelectedCollection", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["libraryEditable"] is True
    assert data["filesEditable"] is True
    assert data["name"] == "My Library"


def test_save_items_creates_item_and_session(
    client: TestClient, article_payload, db_session
):
    """POST /connector/saveItems should create items and record a session."""
    response = client.post("/connector/saveItems", json=article_payload)
    assert response.status_code == 200

    item = db_session.query(Item).filter(Item.doi == "10.1234/example").first()
    assert item is not None
    assert item.title == "Example Paper"
    assert item.item_type == "journalArticle"
    assert item.year == 2024
    assert item.authors == [{"firstName": "Alice", "lastName": "Smith"}]

    session = (
        db_session.query(ConnectorSession)
        .filter(ConnectorSession.session_id == "test-session-1")
        .first()
    )
    assert session is not None
    assert "item1" in session.item_map
    assert session.pending_attachments == ["att1"]


def test_save_items_extracts_arxiv_id_from_archive_id(client: TestClient, db_session):
    """Zotero arXiv translator uses archiveID; we should map it to arxiv_id."""
    payload = {
        "sessionID": "arxiv-test",
        "uri": "https://arxiv.org/abs/2401.00001",
        "items": [
            {
                "id": "item1",
                "itemType": "preprint",
                "title": "An arXiv Preprint",
                "url": "https://arxiv.org/abs/2401.00001",
                "archiveID": "arXiv:2401.00001",
                "DOI": "10.48550/arXiv.2401.00001",
            }
        ],
    }
    response = client.post("/connector/saveItems", json=payload)
    assert response.status_code == 200

    item = db_session.query(Item).filter(Item.title == "An arXiv Preprint").first()
    assert item is not None
    assert item.arxiv_id == "arXiv:2401.00001"


def test_save_attachment_links_file_to_item(
    client: TestClient, article_payload, db_session
):
    """POST /connector/saveAttachment should store a PDF and link it to the parent item."""
    client.post("/connector/saveItems", json=article_payload)

    metadata = json.dumps(
        {
            "id": "att1",
            "parentItemID": "item1",
            "title": "Full Text PDF",
            "contentType": "application/pdf",
        }
    )
    response = client.post(
        "/connector/saveAttachment?sessionID=test-session-1",
        content=b"pdf content",
        headers={"Content-Type": "application/pdf", "X-Metadata": metadata},
    )
    assert response.status_code == 200

    attachment = db_session.query(Attachment).first()
    assert attachment is not None
    assert attachment.content_type == "application/pdf"
    assert attachment.size == 11
    assert attachment.item.title == "Example Paper"

    session = (
        db_session.query(ConnectorSession)
        .filter(ConnectorSession.session_id == "test-session-1")
        .first()
    )
    assert session.pending_attachments == []
    assert "att1" in session.attachment_map


def test_session_progress_tracks_pending_attachments(
    client: TestClient, article_payload, db_session
):
    """sessionProgress should report done=false until attachments are uploaded."""
    client.post("/connector/saveItems", json=article_payload)

    response = client.post(
        "/connector/sessionProgress", json={"sessionID": "test-session-1"}
    )
    assert response.status_code == 200
    assert response.json()["done"] is False

    metadata = json.dumps(
        {
            "id": "att1",
            "parentItemID": "item1",
            "title": "Full Text PDF",
            "contentType": "application/pdf",
        }
    )
    client.post(
        "/connector/saveAttachment?sessionID=test-session-1",
        content=b"pdf content",
        headers={"Content-Type": "application/pdf", "X-Metadata": metadata},
    )

    response = client.post(
        "/connector/sessionProgress", json={"sessionID": "test-session-1"}
    )
    assert response.json()["done"] is True


def test_save_snapshot_creates_webpage_item(client: TestClient, db_session):
    """POST /connector/saveSnapshot should create a webpage item."""
    payload = {
        "sessionID": "snapshot-session",
        "url": "https://example.com/page",
        "title": "Example Page",
    }
    response = client.post("/connector/saveSnapshot", json=payload)
    assert response.status_code == 200

    item = db_session.query(Item).filter(Item.url == "https://example.com/page").first()
    assert item is not None
    assert item.item_type == "webpage"
    assert item.title == "Example Page"


def test_save_snapshot_pdf_creates_document_item(client: TestClient, db_session):
    """POST /connector/saveSnapshot with pdf=true should create a document item."""
    payload = {
        "sessionID": "pdf-session",
        "url": "https://example.com/paper.pdf",
        "title": "Example PDF",
        "pdf": True,
    }
    response = client.post("/connector/saveSnapshot", json=payload)
    assert response.status_code == 200

    item = (
        db_session.query(Item)
        .filter(Item.url == "https://example.com/paper.pdf")
        .first()
    )
    assert item is not None
    assert item.item_type == "document"


def test_save_single_file_stores_snapshot(client: TestClient, db_session):
    """POST /connector/saveSingleFile should store an HTML snapshot attachment."""
    client.post(
        "/connector/saveSnapshot",
        json={
            "sessionID": "snapshot-session",
            "url": "https://example.com/page",
            "title": "Example Page",
            "singleFile": True,
        },
    )

    response = client.post(
        "/connector/saveSingleFile",
        json={
            "sessionID": "snapshot-session",
            "snapshotContent": "<html><body>hello</body></html>",
            "url": "https://example.com/page",
            "title": "Example Page",
        },
    )
    assert response.status_code == 200

    attachment = db_session.query(Attachment).first()
    assert attachment is not None
    assert attachment.content_type == "text/html"
    assert b"<html>" in storage.read_attachment(attachment.storage_path)


def test_save_standalone_attachment_creates_parent(client: TestClient, db_session):
    """POST /connector/saveStandaloneAttachment should create a parent item and attachment."""
    metadata = json.dumps(
        {
            "url": "https://example.com/standalone.pdf",
            "title": "Standalone PDF",
            "contentType": "application/pdf",
        }
    )
    response = client.post(
        "/connector/saveStandaloneAttachment?sessionID=standalone-session",
        content=b"standalone pdf",
        headers={"Content-Type": "application/pdf", "X-Metadata": metadata},
    )
    assert response.status_code == 200
    assert response.json()["canRecognize"] is False

    item = (
        db_session.query(Item)
        .filter(Item.url == "https://example.com/standalone.pdf")
        .first()
    )
    assert item is not None
    assert item.item_type == "document"

    attachment = db_session.query(Attachment).first()
    assert attachment is not None
    assert attachment.item_id == item.id


def test_has_attachment_resolvers_returns_false(client: TestClient):
    """POST /connector/hasAttachmentResolvers should return false."""
    response = client.post(
        "/connector/hasAttachmentResolvers",
        json={"sessionID": "test", "itemID": "item1"},
    )
    assert response.status_code == 200
    assert response.json() is False


def test_delay_sync_is_noop(client: TestClient):
    """POST /connector/delaySync should return an empty object."""
    response = client.post("/connector/delaySync", json={})
    assert response.status_code == 200
    assert response.json() == {}
