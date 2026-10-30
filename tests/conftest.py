import os
import sys
from datetime import datetime, timedelta, timezone

# 1. Ensure project root is on sys.path before local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import security
from database import Base, get_db
from main import app
from models import AccessTokenModel, ClientModel

# 2. In-memory SQLite configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh schema for each individual test and tear it down afterward."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient overriding get_db to point to SQLite in-memory."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_headers(monkeypatch):
    """Mocks ADMIN_SECRET_KEY for testing administrative routes."""
    test_key = "test_admin_secret_key_123"
    monkeypatch.setattr(security, "ADMIN_SECRET_KEY", test_key)
    return {"X-Admin-Key": test_key}


@pytest.fixture(scope="function")
def active_client_fixture(db_session):
    """Seeds a test client and an active 24-hour access token."""
    client_id = "test_client_abc"
    token = "test_valid_token_123456"

    db_client = ClientModel(
        client_id=client_id,
        client_secret="test_secret_999",
        name="Test Automation Corp",
        email="testcorp@example.com",
        is_active=True,
    )
    db_session.add(db_client)

    access_token = AccessTokenModel(
        token=token,
        client_id=client_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db_session.add(access_token)
    db_session.commit()

    return {
        "client_id": client_id,
        "token": token,
        "headers": {"X-Token": token},
    }