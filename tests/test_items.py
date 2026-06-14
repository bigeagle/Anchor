"""Tests for item CRUD endpoints."""

import uuid

import pytest
from fastapi.testclient import TestClient


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
    response = client.get(f"/items/{uuid.uuid4()}")
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
    response = client.put(f"/items/{uuid.uuid4()}", json={"title": "X"})
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
    response = client.delete(f"/items/{uuid.uuid4()}")
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
