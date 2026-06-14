"""Tests for translator caching and serving (Phase 2.2)."""

import json

import pytest
from fastapi.testclient import TestClient

from anchor_server.services import translator_service


@pytest.fixture
def sample_translator(translators_dir):
    """Write a cached translator file pair into the temp translators directory."""
    metadata = {
        "translatorID": "ecddda2e-4fc6-4aea-9f17-ef3b56d7377a",
        "label": "arXiv.org",
        "creator": "Test",
        "target": "^https?://arxiv\\.org/",
        "minVersion": "3.0",
        "maxVersion": "",
        "priority": 100,
        "translatorType": 4,
        "browserSupport": "gcsibv",
        "inRepository": True,
        "lastUpdated": "2026-05-19 15:28:10",
    }
    code = '{"translatorID": "ecddda2e-4fc6-4aea-9f17-ef3b56d7377a"}\n// code'
    (translators_dir / "metadata.json").write_text(
        json.dumps([metadata]), encoding="utf-8"
    )
    (translators_dir / "arXiv_org.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    (translators_dir / "arXiv_org.js").write_text(code, encoding="utf-8")
    return metadata


def test_list_translators_filters_properties(translators_dir, sample_translator):
    """list_translators should return only the properties the connector needs."""
    items = translator_service.list_translators()
    assert len(items) == 1
    item = items[0]
    assert item["translatorID"] == sample_translator["translatorID"]
    assert item["label"] == "arXiv.org"
    assert "lastUpdated" in item
    # Only connector-relevant properties are exposed.
    assert set(item.keys()) <= translator_service._TRANSLATOR_CACHING_PROPERTIES


def test_get_translator_code_returns_source(translators_dir, sample_translator):
    """get_translator_code should return the cached JavaScript source."""
    code = translator_service.get_translator_code(sample_translator["translatorID"])
    assert "// code" in code


def test_get_translator_code_missing_raises(translators_dir):
    """get_translator_code should raise FileNotFoundError for unknown IDs."""
    with pytest.raises(FileNotFoundError):
        translator_service.get_translator_code("00000000-0000-0000-0000-000000000000")


def test_get_translators_hash_is_stable(translators_dir, sample_translator):
    """get_translators_hash should return the same value for the same cache."""
    h1 = translator_service.get_translators_hash()
    h2 = translator_service.get_translators_hash()
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 32


def test_get_proxies_returns_empty_without_config(monkeypatch):
    """get_proxy_list should return an empty list when no proxy is configured."""
    monkeypatch.setattr(translator_service.settings, "http_proxy", None)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    assert translator_service.get_proxy_list() == []


def test_get_client_hostnames():
    """get_client_hostnames should include localhost."""
    hostnames = translator_service.get_client_hostnames()
    assert "localhost" in hostnames


def test_get_translators_endpoint(
    client: TestClient, translators_dir, sample_translator
):
    """POST /connector/getTranslators should return cached metadata."""
    response = client.post("/connector/getTranslators", json={})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["translatorID"] == sample_translator["translatorID"]


def test_get_translator_code_endpoint(
    client: TestClient, translators_dir, sample_translator
):
    """POST /connector/getTranslatorCode should return JavaScript source."""
    response = client.post(
        "/connector/getTranslatorCode",
        json={"translatorID": sample_translator["translatorID"]},
    )
    assert response.status_code == 200
    assert "// code" in response.text


def test_ping_includes_translators_hash(
    client: TestClient, translators_dir, sample_translator
):
    """POST /connector/ping should include translator hash prefs."""
    response = client.post("/connector/ping", json={})
    assert response.status_code == 200
    prefs = response.json()["prefs"]
    assert "translatorsHash" in prefs
    assert "sortedTranslatorHash" in prefs


def test_proxies_endpoint(client: TestClient, monkeypatch):
    """GET /connector/proxies should return an array."""
    monkeypatch.setattr(translator_service.settings, "http_proxy", None)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    response = client.get("/connector/proxies")
    assert response.status_code == 200
    assert response.json() == []


def test_get_client_hostnames_endpoint(client: TestClient):
    """GET /connector/getClientHostnames should return hostnames."""
    response = client.get("/connector/getClientHostnames")
    assert response.status_code == 200
    assert "localhost" in response.json()
