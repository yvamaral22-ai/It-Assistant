import re
from datetime import datetime

from sqlalchemy import select

from app.models import AuditLog, InternalNotice
from app.services.auth_service import AuthService
from app.services.datetime_service import format_local_datetime


def csrf_from(response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login(client, username: str, password: str) -> None:
    page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf": csrf_from(page)},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_notices_control_requires_authentication(client):
    response = client.get("/admin/control/notices", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_notice_timestamps_use_sao_paulo_time():
    utc_value = datetime(2026, 7, 15, 17, 31)
    assert format_local_datetime(utc_value) == "15/07/2026 14:31"


def test_master_publishes_notice(authenticated_client):
    client = authenticated_client
    page = client.get("/admin/control/notices")
    assert page.status_code == 200
    response = client.post(
        "/admin/control/notices",
        data={
            "csrf": csrf_from(page),
            "title": "Orientação importante",
            "message": "Consulte o autoatendimento antes de abrir um chamado.",
            "severity": "info",
            "is_active": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    home = client.get("/")
    assert "Orientação importante" in home.text
    assert "Consulte o autoatendimento antes de abrir" in home.text
    assert "Status dos serviços" not in home.text

    with client.db_factory() as db:
        assert db.scalar(select(InternalNotice).where(InternalNotice.severity == "info"))
        assert db.scalar(select(AuditLog).where(AuditLog.action == "notices.created"))


def test_inactive_notice_is_not_public(authenticated_client):
    client = authenticated_client
    page = client.get("/admin/control/notices")
    client.post(
        "/admin/control/notices",
        data={
            "csrf": csrf_from(page), "title": "Aviso oculto",
            "message": "Não publicar", "severity": "info",
        },
    )
    assert "Aviso oculto" not in client.get("/").text


def test_analyst_can_read_but_cannot_change_notices(client):
    password = "Temporary-password-2026"
    with client.db_factory() as db:
        AuthService(db).create_user("analyst.notices", password, "analyst")
    login(client, "analyst.notices", password)
    page = client.get("/admin/control/notices")
    assert page.status_code == 200
    response = client.post(
        "/admin/control/notices",
        data={
            "csrf": "not-used-without-write-permission", "title": "Bloqueado",
            "message": "Sem permissão", "severity": "info", "is_active": "true",
        },
    )
    assert response.status_code == 403
