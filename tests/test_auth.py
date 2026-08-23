"""Tests for API token authentication."""

import pytest
from fastapi.testclient import TestClient

from anchor_server.config import settings
from anchor_server.models import ApiToken
from anchor_server.security import ensure_api_token, hash_token

SECRET = "test-secret-token"


@pytest.fixture
def auth_enabled(client: TestClient, db_session, monkeypatch):
    """Enable auth and seed a known token in the test database."""
    monkeypatch.setattr(settings, "auth_enabled", True)
    db_session.add(ApiToken(token_hash=hash_token(SECRET)))
    db_session.commit()
    return client


def test_auth_disabled_by_default(client: TestClient):
    """Without ANCHOR_AUTH_ENABLED, endpoints stay open."""
    assert client.get("/api/v1/items/").status_code == 200


def test_missing_token_rejected(auth_enabled: TestClient):
    """Requests without a bearer token should get 401."""
    response = auth_enabled.get("/api/v1/items/")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_wrong_token_rejected(auth_enabled: TestClient):
    """Requests with an unknown token should get 401."""
    response = auth_enabled.get(
        "/api/v1/items/", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_valid_token_accepted(auth_enabled: TestClient):
    """Requests with the seeded token should pass."""
    response = auth_enabled.get(
        "/api/v1/items/", headers={"Authorization": f"Bearer {SECRET}"}
    )
    assert response.status_code == 200


def test_healthz_stays_open(auth_enabled: TestClient):
    """The health check endpoint must not require auth."""
    assert auth_enabled.get("/api/v1/healthz").status_code == 200


def test_ensure_api_token_generates_once(db_session):
    """First call generates a token, later calls keep the existing one."""
    token = ensure_api_token(db_session)
    assert token  # plaintext returned exactly once
    assert db_session.query(ApiToken).count() == 1

    assert ensure_api_token(db_session) is None
    assert db_session.query(ApiToken).count() == 1

    # The stored hash authenticates the generated token.
    row = db_session.query(ApiToken).first()
    assert row.token_hash == hash_token(token)
    assert row.token_hash != token  # never stored in plaintext


def test_ensure_api_token_seeds_from_config(db_session, monkeypatch):
    """ANCHOR_API_TOKEN seeds the stored hash instead of generating one."""
    monkeypatch.setattr(settings, "api_token", "configured-token")
    assert ensure_api_token(db_session) is None
    row = db_session.query(ApiToken).first()
    assert row.token_hash == hash_token("configured-token")
