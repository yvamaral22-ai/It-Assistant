import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings, resolve_data_path
from app.database import Base, get_db
from app.main import app
from app.services.auth_service import AuthService


@pytest.fixture
def client():
    rate_limit_store = resolve_data_path(get_settings().rate_limit_store_path)
    rate_limit_store.unlink(missing_ok=True)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        test_client.db_factory = TestingSession
        yield test_client
    app.dependency_overrides.clear()
    rate_limit_store.unlink(missing_ok=True)


@pytest.fixture
def session_payload():
    return {
        "user_name": "Usuário Teste",
        "department": "TI",
        "location": "Matriz",
        "computer_name": "PC-01",
        "issue_type": "Falha ao iniciar",
        "category": "excel",
        "initial_description": "Excel não abre",
    }


@pytest.fixture
def authenticated_client(client):
    password = "A-strong-local-password-2026"
    with client.db_factory() as db:
        AuthService(db).create_or_reset_master("master", password)
    page = client.get("/admin/login")
    match = re.search(r'name="csrf" value="([^"]+)"', page.text)
    assert match
    response = client.post(
        "/admin/login",
        data={"username": "master", "password": password, "csrf": match.group(1)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client
