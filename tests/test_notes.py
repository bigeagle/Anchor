"""Tests for the read-only notes feature (linked markdown per item)."""

from anchor_server.config import settings

API = "/api/v1"


def _create_item(client, **overrides) -> str:
    payload = {"title": "A paper", "authors": [{"name": "Alice"}]}
    payload.update(overrides)
    response = client.post(f"{API}/items/", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def _write_note(relative_path: str, content: str = "# Hello\n") -> None:
    path = settings.notes_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_note_path_roundtrip(client):
    item_id = _create_item(client)

    response = client.put(f"{API}/items/{item_id}", json={"note_path": "papers/a.md"})
    assert response.status_code == 200
    assert response.json()["note_path"] == "papers/a.md"
    assert response.json()["note_available"] is False

    _write_note("papers/a.md")
    response = client.get(f"{API}/items/{item_id}")
    assert response.json()["note_available"] is True

    # Explicit null clears the link.
    response = client.put(f"{API}/items/{item_id}", json={"note_path": None})
    assert response.status_code == 200
    assert response.json()["note_path"] is None
    assert response.json()["note_available"] is False


def test_get_item_note(client):
    _write_note("papers/a.md", "# Title\n\n![[img.png|alt text]]\n")
    item_id = _create_item(client, note_path="papers/a.md")

    response = client.get(f"{API}/items/{item_id}/note")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text == "# Title\n\n![[img.png|alt text]]\n"


def test_get_item_note_not_linked(client):
    item_id = _create_item(client)
    response = client.get(f"{API}/items/{item_id}/note")
    assert response.status_code == 404
    assert "no linked note" in response.json()["detail"]


def test_get_item_note_file_missing(client):
    item_id = _create_item(client, note_path="papers/missing.md")
    response = client.get(f"{API}/items/{item_id}/note")
    assert response.status_code == 404
    assert "not available" in response.json()["detail"]


def test_get_item_note_invalid_path(client):
    item_id = _create_item(client, note_path="../outside.md")
    response = client.get(f"{API}/items/{item_id}/note")
    assert response.status_code == 400


def test_note_asset(client):
    _write_note("assets/img.png", "fake-png-bytes")

    response = client.get(f"{API}/notes/assets/assets/img.png")
    assert response.status_code == 200
    assert response.content == b"fake-png-bytes"
    assert response.headers["content-type"] == "image/png"


def test_note_asset_rejects_traversal(client):
    response = client.get(f"{API}/notes/assets/..%2F..%2Fanchor.db")
    assert response.status_code in {400, 404}


def test_note_asset_rejects_non_image(client):
    _write_note("papers/a.md")
    response = client.get(f"{API}/notes/assets/papers/a.md")
    assert response.status_code == 404


def test_note_asset_missing(client):
    response = client.get(f"{API}/notes/assets/nope.png")
    assert response.status_code == 404


def test_note_asset_lookup_by_name(client):
    _write_note("papers/deep/img.svg", "<svg/>")

    response = client.get(f"{API}/notes/lookup/img.svg")
    assert response.status_code == 200
    assert response.content == b"<svg/>"


def test_note_asset_lookup_missing(client):
    response = client.get(f"{API}/notes/lookup/nope.png")
    assert response.status_code == 404


def test_note_asset_lookup_rejects_non_image(client):
    _write_note("papers/a.md")
    response = client.get(f"{API}/notes/lookup/a.md")
    assert response.status_code == 404
