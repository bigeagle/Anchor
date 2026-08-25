"""Tests for item CRUD endpoints."""

import json
import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from anchor_server.models import Item


@pytest.fixture
def sample_item_payload():
    """Return a valid create-payload for an item."""
    return {
        "title": "Test Paper",
        "item_type": "journalArticle",
        "authors": [{"firstName": "Alice", "lastName": "Smith"}],
        "year": 2024,
        "doi": "10.1234/example",
        "arxiv_id": "arXiv:2401.00001",
    }


def test_create_item(client: TestClient, sample_item_payload):
    """POST /items should create and return the new item."""
    response = client.post("/api/v1/items/", json=sample_item_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == sample_item_payload["title"]
    assert data["item_type"] == sample_item_payload["item_type"]
    assert data["authors"] == sample_item_payload["authors"]
    assert "id" in data
    assert "date_added" in data


def test_list_items(client: TestClient, sample_item_payload):
    """GET /items should return created items with optional filtering."""
    client.post("/api/v1/items/", json=sample_item_payload)

    response = client.get("/api/v1/items/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == sample_item_payload["title"]

    response = client.get("/api/v1/items/?q=Nonexistent")
    assert response.json() == []


def test_get_item(client: TestClient, sample_item_payload):
    """GET /items/{id} should return a single item."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    item_id = created["id"]

    response = client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_get_item_not_found(client: TestClient):
    """GET /items/{id} with unknown id should return 404."""
    response = client.get(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404


def test_update_item(client: TestClient, sample_item_payload):
    """PUT /items/{id} should update allowed fields."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    item_id = created["id"]

    response = client.put(f"/api/v1/items/{item_id}", json={"title": "Updated Title"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["year"] == sample_item_payload["year"]


def test_update_item_not_found(client: TestClient):
    """PUT /items/{id} with unknown id should return 404."""
    response = client.put(f"/api/v1/items/{uuid.uuid4()}", json={"title": "X"})
    assert response.status_code == 404


def test_delete_item(client: TestClient, sample_item_payload):
    """DELETE /items/{id} should remove the item."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    item_id = created["id"]

    response = client.delete(f"/api/v1/items/{item_id}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/items/{item_id}")
    assert response.status_code == 404


def test_delete_item_not_found(client: TestClient):
    """DELETE /items/{id} with unknown id should return 404."""
    response = client.delete(f"/api/v1/items/{uuid.uuid4()}")
    assert response.status_code == 404


def test_create_item_validation(client: TestClient):
    """Creating an item without a title should fail validation."""
    response = client.post("/api/v1/items/", json={"title": ""})
    assert response.status_code == 422


def test_create_item_invalid_type(client: TestClient):
    """An unsupported item_type should fail validation."""
    response = client.post(
        "/api/v1/items/",
        json={"title": "Bad Type", "item_type": "notARealType"},
    )
    assert response.status_code == 422


def test_update_item_type(client: TestClient, sample_item_payload):
    """Updating item_type to another valid enum value should work."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    item_id = created["id"]

    response = client.put(f"/api/v1/items/{item_id}", json={"item_type": "book"})
    assert response.status_code == 200
    assert response.json()["item_type"] == "book"


def test_arxiv_id_persisted(client: TestClient, sample_item_payload):
    """arxiv_id should be saved and returned as a top-level field."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    assert created["arxiv_id"] == sample_item_payload["arxiv_id"]

    item_id = created["id"]
    response = client.get(f"/api/v1/items/{item_id}")
    assert response.json()["arxiv_id"] == sample_item_payload["arxiv_id"]


def test_search_items(client: TestClient, sample_item_payload):
    """GET /search should match items by title, arxiv_id, authors, or url."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()

    # Title substring
    response = client.get("/api/v1/search/?q=Test")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == created["id"]

    # arxiv_id
    response = client.get("/api/v1/search/?q=2401.00001")
    assert response.status_code == 200
    assert response.json()[0]["id"] == created["id"]

    # Author last name
    response = client.get("/api/v1/search/?q=Smith")
    assert response.status_code == 200
    assert response.json()[0]["id"] == created["id"]

    # DOI prefix
    response = client.get("/api/v1/search/?q=10.1234")
    assert response.status_code == 200
    assert response.json()[0]["id"] == created["id"]


def test_search_without_trailing_slash(client: TestClient, sample_item_payload):
    """GET /search (no slash) must hit the API, not the SPA fallback."""
    client.post("/api/v1/items/", json=sample_item_payload)
    response = client.get("/api/v1/search?q=Test")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert len(response.json()) == 1


def test_items_without_trailing_slash(client: TestClient, sample_item_payload):
    """GET/POST /items (no slash) must hit the API, not the SPA fallback."""
    response = client.post("/api/v1/items", json=sample_item_payload)
    assert response.status_code == 201
    response = client.get("/api/v1/items")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_search_no_match(client: TestClient, sample_item_payload):
    """GET /search with a non-matching term should return an empty list."""
    client.post("/api/v1/items/", json=sample_item_payload)
    response = client.get("/api/v1/search/?q=NonexistentTerm123")
    assert response.status_code == 200
    assert response.json() == []


def test_search_missing_query(client: TestClient):
    """GET /search without the required q parameter should return 422."""
    response = client.get("/api/v1/search/")
    assert response.status_code == 422


def test_list_items_sorted_by_year(client: TestClient, db_session):
    """GET /items should support order_by and sort parameters."""
    # Create items with different years.
    for title, year in [("Old", 2000), ("New", 2024), ("Mid", 2010)]:
        item = Item(title=title, item_type="journalArticle", year=year)
        db_session.add(item)
    db_session.commit()

    response = client.get("/api/v1/items/?order_by=year&sort=desc")
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()]
    assert titles == ["New", "Mid", "Old"]

    response = client.get("/api/v1/items/?order_by=year&sort=asc")
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()]
    assert titles == ["Old", "Mid", "New"]


def test_list_items_sorted_by_title(client: TestClient, db_session):
    """GET /items should sort by title."""
    for title in ["Beta", "Alpha", "Gamma"]:
        item = Item(title=title, item_type="journalArticle")
        db_session.add(item)
    db_session.commit()

    response = client.get("/api/v1/items/?order_by=title&sort=asc")
    assert response.status_code == 200
    titles = [i["title"] for i in response.json()]
    assert titles == ["Alpha", "Beta", "Gamma"]


def test_list_items_invalid_order_by(client: TestClient):
    """GET /items should reject unknown order_by fields."""
    response = client.get("/api/v1/items/?order_by=unknown")
    assert response.status_code == 400


def test_update_item_bumps_version(client: TestClient, sample_item_payload):
    """Each update should increment the item version."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    assert created["version"] == 1

    updated = client.put(f"/api/v1/items/{created['id']}", json={"title": "V2"}).json()
    assert updated["version"] == 2

    updated = client.put(f"/api/v1/items/{created['id']}", json={"year": 1999}).json()
    assert updated["version"] == 3


def test_delete_item_is_soft_delete(
    client: TestClient, db_session, sample_item_payload
):
    """DELETE should leave a tombstone row and hide the item from list/search."""
    created = client.post("/api/v1/items/", json=sample_item_payload).json()
    item_id = created["id"]

    response = client.delete(f"/api/v1/items/{item_id}")
    assert response.status_code == 204

    item = db_session.get(Item, uuid.UUID(item_id))
    assert item is not None
    assert item.deleted_at is not None
    assert item.version == created["version"] + 1

    assert client.get("/api/v1/items/").json() == []
    response = client.get("/api/v1/search/?q=Test")
    assert response.json() == []


def test_create_item_with_attachment(client: TestClient, sample_item_payload):
    """POST /items/with-attachment should create item and attachment atomically."""
    response = client.post(
        "/api/v1/items/with-attachment",
        data={"metadata": json.dumps(sample_item_payload)},
        files={"file": ("paper.pdf", BytesIO(b"pdf bytes"), "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Paper"
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["content_type"] == "application/pdf"


def test_create_item_with_attachment_duplicate_leaves_nothing(
    client: TestClient, db_session, sample_item_payload
):
    """A duplicate upload should 409 without creating any rows."""
    from anchor_server.models import Attachment

    first = client.post(
        "/api/v1/items/with-attachment",
        data={"metadata": json.dumps(sample_item_payload)},
        files={"file": ("paper.pdf", BytesIO(b"pdf bytes"), "application/pdf")},
    )
    assert first.status_code == 201

    response = client.post(
        "/api/v1/items/with-attachment",
        data={"metadata": json.dumps(sample_item_payload)},
        files={"file": ("paper2.pdf", BytesIO(b"pdf bytes"), "application/pdf")},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["existing_item_id"] == first.json()["id"]
    assert detail["existing_item_title"] == "Test Paper"

    # No orphan item or attachment left behind.
    assert db_session.query(Item).count() == 1
    assert db_session.query(Attachment).count() == 1


def test_create_item_with_attachment_invalid_metadata(client: TestClient):
    """Malformed metadata JSON should return 422."""
    response = client.post(
        "/api/v1/items/with-attachment",
        data={"metadata": '{"title": 42}'},
        files={"file": ("paper.pdf", BytesIO(b"x"), "application/pdf")},
    )
    assert response.status_code == 422
