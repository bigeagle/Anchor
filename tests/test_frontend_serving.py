"""Tests for serving the frontend SPA from the backend (Phase 3)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anchor_server.main import SPAStaticFiles


def make_dist(tmp_path: Path) -> Path:
    """Create a minimal dist directory with an index.html and one asset."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html><body>Anchor SPA</body></html>")
    (dist / "assets" / "app.js").write_text("console.log('hi');")
    return dist


def make_client(dist: Path) -> TestClient:
    """App wiring mirroring anchor_server.main: API routes first, SPA last."""
    app = FastAPI()

    @app.get("/api/v1/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.mount("/", SPAStaticFiles(directory=dist, html=True), name="frontend")
    return TestClient(app)


def test_root_serves_index_html(tmp_path: Path) -> None:
    client = make_client(make_dist(tmp_path))
    response = client.get("/")
    assert response.status_code == 200
    assert "Anchor SPA" in response.text


def test_spa_fallback_for_client_side_route(tmp_path: Path) -> None:
    client = make_client(make_dist(tmp_path))
    response = client.get("/items/4803eb5e-1396-4c10-b405-42cd8fbd1df7")
    assert response.status_code == 200
    assert "Anchor SPA" in response.text


def test_static_asset_served_directly(tmp_path: Path) -> None:
    client = make_client(make_dist(tmp_path))
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert response.text == "console.log('hi');"


def test_api_routes_take_precedence_over_spa(tmp_path: Path) -> None:
    client = make_client(make_dist(tmp_path))
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
