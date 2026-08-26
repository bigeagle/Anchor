"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from anchor_server.config import settings
from anchor_server.database import Base, get_db
from anchor_server.main import app


@pytest.fixture(autouse=True)
def _default_settings(monkeypatch):
    """Isolate tests from the developer's real .env (role, auth, sync)."""
    monkeypatch.setattr(settings, "role", "standalone")
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "central_url", None)
    monkeypatch.setattr(settings, "sync_token", None)


@pytest.fixture
def engine():
    """Create an isolated in-memory SQLite engine and tables for each test."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(engine):
    """Provide a database session bound to the isolated test engine."""
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    session = testing_session_local()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Use a temporary directory for file attachments during tests."""
    data_dir = (tmp_path / "data").resolve()
    data_dir.mkdir()
    attachments_dir = (tmp_path / "attachments").resolve()
    attachments_dir.mkdir()
    translators_dir = (tmp_path / "translators").resolve()
    translators_dir.mkdir()
    markdown_cache_dir = (tmp_path / "cache" / "markdown").resolve()
    markdown_cache_dir.mkdir(parents=True)
    notes_dir = (tmp_path / "notes").resolve()
    notes_dir.mkdir()
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(settings, "attachments_dir", attachments_dir)
    monkeypatch.setattr(settings, "notes_dir", notes_dir)
    monkeypatch.setattr(settings, "translators_dir", translators_dir)
    monkeypatch.setattr(settings, "markdown_cache_dir", markdown_cache_dir)
    # Ensure tests use the default naming template regardless of local .env files.
    monkeypatch.setattr(
        settings,
        "attachment_name_template",
        "{{ year }}_{{ authors_last_names }}_{{ title_slug }}",
    )
    return data_dir


@pytest.fixture
def translators_dir(temp_data_dir):
    """Return the temporary translators directory used during tests."""
    return settings.translators_dir


@pytest.fixture
def client(db_session, temp_data_dir):
    """Build a TestClient with the test database session injected."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
