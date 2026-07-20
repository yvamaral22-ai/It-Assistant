import re

from app.services.auth_service import AuthService, hash_password, verify_password


def csrf_from(response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def create_master(client, password="A-strong-local-password-2026"):
    with client.db_factory() as db:
        return AuthService(db).create_or_reset_master("master", password)


def login(client, password="A-strong-local-password-2026"):
    page = client.get("/admin/login")
    return client.post(
        "/admin/login",
        data={"username": "master", "password": password, "csrf": csrf_from(page)},
        follow_redirects=False,
    )


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("A-strong-local-password-2026")
    second = hash_password("A-strong-local-password-2026")
    assert first != second
    assert first.startswith("scrypt$32768$8$3$")
    assert verify_password("A-strong-local-password-2026", first)
    assert not verify_password("wrong-password", first)


def test_control_requires_master_login(client):
    response = client.get("/admin/control", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_history_reports_and_export_require_login(client):
    for path in ("/admin/sessions", "/admin/reports", "/admin/reports/export.csv"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/login"


def test_master_can_access_history_reports_and_export(authenticated_client):
    for path in ("/admin/sessions", "/admin/reports", "/admin/reports/export.csv"):
        response = authenticated_client.get(path)
        assert response.status_code == 200


def test_login_returns_to_original_protected_page(client):
    create_master(client)
    blocked = client.get("/admin/reports", follow_redirects=False)
    assert blocked.status_code == 303
    response = login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/reports"


def test_master_can_login_and_open_control(client):
    create_master(client)
    response = login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/control"
    control = client.get("/admin/control")
    assert control.status_code == 200
    assert "Painel de controle" in control.text
    assert "Fluxos de diagnóstico" in control.text


def test_invalid_login_is_rejected(client):
    create_master(client)
    response = login(client, "incorrect-password")
    assert response.status_code == 401
    assert "Usuário ou senha inválidos" in response.text


def test_editor_rejects_invalid_json_without_overwriting(client):
    create_master(client)
    login(client)
    page = client.get("/admin/control/knowledge/excel")
    response = client.post(
        "/admin/control/knowledge/excel",
        data={"csrf": csrf_from(page), "content": "{invalid"},
    )
    assert response.status_code == 422
    assert "Rascunho rejeitado" in response.text


def test_csrf_is_required_for_password_change(client):
    create_master(client)
    login(client)
    response = client.post(
        "/admin/control/password",
        data={
            "csrf": "invalid",
            "current_password": "A-strong-local-password-2026",
            "new_password": "Another-strong-password-2026",
            "confirmation": "Another-strong-password-2026",
        },
    )
    assert response.status_code == 403
