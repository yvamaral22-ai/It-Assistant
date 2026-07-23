import re

from sqlalchemy import select

from app.models import AuditLog
from app.services.auth_service import AuthService


def csrf_from(response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login_as(client, username: str, password: str = "Temporary-password-2026") -> None:
    client.cookies.clear()
    page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf": csrf_from(page)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def create_role_users(client) -> None:
    with client.db_factory() as db:
        service = AuthService(db)
        service.create_or_reset_master("master", "Temporary-password-2026")
        for username, role in (
            ("analyst.matrix", "analyst"),
            ("editor.matrix", "editor"),
            ("reader.matrix", "reader"),
        ):
            service.create_user(username, "Temporary-password-2026", role)


def test_admin_permission_matrix_is_enforced(client):
    create_role_users(client)
    expectations = {
        "master": {
            "/admin/sessions": 200,
            "/admin/reports": 200,
            "/admin/reports/export.csv": 200,
            "/admin/control/users": 200,
            "/admin/control/knowledge/excel": 200,
            "/admin/control/notices": 200,
            "/admin/control/processes": 200,
            "/admin/control/audit": 200,
        },
        "analyst.matrix": {
            "/admin/sessions": 200,
            "/admin/reports": 200,
            "/admin/reports/export.csv": 200,
            "/admin/control/users": 403,
            "/admin/control/knowledge/excel": 403,
            "/admin/control/notices": 200,
            "/admin/control/processes": 403,
            "/admin/control/audit": 403,
        },
        "editor.matrix": {
            "/admin/sessions": 403,
            "/admin/reports": 403,
            "/admin/reports/export.csv": 403,
            "/admin/control/users": 403,
            "/admin/control/knowledge/excel": 200,
            "/admin/control/notices": 200,
            "/admin/control/processes": 403,
            "/admin/control/audit": 403,
        },
        "reader.matrix": {
            "/admin/sessions": 200,
            "/admin/reports": 200,
            "/admin/reports/export.csv": 403,
            "/admin/control/users": 403,
            "/admin/control/knowledge/excel": 403,
            "/admin/control/notices": 403,
            "/admin/control/processes": 403,
            "/admin/control/audit": 403,
        },
    }
    for username, routes in expectations.items():
        login_as(client, username)
        for path, status in routes.items():
            assert client.get(path, follow_redirects=False).status_code == status, (username, path)


def test_admin_state_changes_require_csrf(authenticated_client):
    checks = (
        ("/admin/control/password", {
            "csrf": "invalid",
            "current_password": "A-strong-local-password-2026",
            "new_password": "Another-strong-password-2026",
            "confirmation": "Another-strong-password-2026",
        }),
        ("/admin/control/users", {
            "csrf": "invalid",
            "username": "csrf.blocked",
            "password": "Temporary-password-2026",
            "role": "reader",
        }),
        ("/admin/control/notices", {
            "csrf": "invalid",
            "title": "Bloqueado",
            "message": "Sem CSRF",
            "severity": "info",
            "is_active": "true",
        }),
        ("/admin/control/processes", {
            "csrf": "invalid",
            "title": "Bloqueado",
            "content": "Sem CSRF",
            "display_order": "1",
            "is_active": "true",
        }),
    )
    for path, data in checks:
        assert authenticated_client.post(path, data=data, follow_redirects=False).status_code == 403


def test_untrusted_user_input_is_escaped_in_admin_and_public_pages(authenticated_client):
    client = authenticated_client
    payload = {
        "user_name": '<script>alert("x")</script>',
        "department": "<img src=x onerror=alert(1)>",
        "location": "Matriz",
        "computer_name": "pc-xss",
        "issue_type": "<b>Falha</b>",
        "category": "excel",
        "initial_description": '<svg onload=alert("x")>',
    }
    created = client.post("/api/sessions", json=payload)
    assert created.status_code == 201
    session_id = created.json()["session"]["id"]
    admin_page = client.get(f"/admin/sessions/{session_id}")
    assert admin_page.status_code == 200
    assert "<script>alert" not in admin_page.text
    assert "&lt;script&gt;" in admin_page.text
    assert "<svg onload" not in admin_page.text


def test_csv_export_escapes_formula_payloads(authenticated_client):
    payload = {
        "user_name": "=HYPERLINK(\"http://evil.local\",\"click\")",
        "department": "+cmd",
        "location": "-2+3",
        "computer_name": "@SUM(1,1)",
        "issue_type": "Excel",
        "category": "excel",
        "initial_description": "=1+1",
    }
    created = authenticated_client.post("/api/sessions", json=payload)
    assert created.status_code == 201
    exported = authenticated_client.get("/admin/reports/export.csv")
    assert exported.status_code == 200
    assert "'=HYPERLINK" in exported.text
    assert "'+cmd" in exported.text
    assert "'-2+3" in exported.text
    assert "'@SUM" in exported.text
    with authenticated_client.db_factory() as db:
        assert db.scalar(select(AuditLog).where(AuditLog.action == "reports.exported"))
