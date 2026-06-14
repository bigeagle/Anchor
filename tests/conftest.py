"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from anchor_server.config import settings
from anchor_server.database import Base, get_db
from anchor_server.main import app


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
    monkeypatch.setattr(settings, "data_dir", data_dir)
    monkeypatch.setattr(settings, "attachments_dir", attachments_dir)
    return data_dir


@pytest.fixture
def client(db_session, temp_data_dir):
    """Build a TestClient with the test database session injected."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
