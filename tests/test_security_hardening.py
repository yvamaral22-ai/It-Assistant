import pytest
from sqlalchemy import select

from app.config import Settings, get_session_secret
from app.models import User
from app.services.auth_service import AuthService
from app.services.security_service import validate_security_settings


def test_dynamic_responses_send_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["permissions-policy"]
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_untrusted_host_and_cross_origin_write_are_rejected(client, session_payload):
    assert client.get("/", headers={"host": "attacker.example"}).status_code == 400
    response = client.post(
        "/api/sessions",
        json=session_payload,
        headers={"origin": "http://attacker.example"},
    )
    assert response.status_code == 403


def test_oversized_request_is_rejected_before_parsing(client):
    response = client.post(
        "/api/sessions",
        content=b"x" * 1_048_577,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_public_session_response_is_minimal_and_bound_to_browser(client, session_payload):
    created = client.post("/api/sessions", json=session_payload)
    assert created.status_code == 201
    public_session = created.json()["session"]
    assert set(public_session) == {"id", "category", "status", "current_node_id"}
    session_id = public_session["id"]

    client.cookies.clear()
    assert client.get(f"/api/sessions/{session_id}").status_code == 404
    assert client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    ).status_code == 404


def test_password_reset_invalidates_existing_admin_session(authenticated_client):
    client = authenticated_client
    assert client.get("/admin/control").status_code == 200
    with client.db_factory() as db:
        user = db.scalar(select(User).where(User.username == "master"))
        AuthService(db).reset_password(user, "Replacement-password-2026")

    response = client.get("/admin/control", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_production_rejects_default_secret_and_non_https_origin():
    insecure = Settings(
        _env_file=None,
        app_env="production",
        secret_key="change-this-value",
        public_base_url="http://assistant.internal",
        allowed_hosts="assistant.internal",
    )
    with pytest.raises(RuntimeError, match="HTTPS"):
        validate_security_settings(insecure)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        get_session_secret(insecure)
