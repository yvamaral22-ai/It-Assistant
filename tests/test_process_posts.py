import re

from sqlalchemy import select

from app.config import BASE_DIR
from app.models import AuditLog, ProcessPost
from app.services.auth_service import AuthService


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


def test_process_editor_requires_authentication(client):
    response = client.get("/admin/control/processes", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_master_can_create_update_and_delete_process_post(authenticated_client):
    client = authenticated_client
    page = client.get("/admin/control/processes")
    csrf = csrf_from(page)

    created = client.post(
        "/admin/control/processes",
        data={
            "csrf": csrf,
            "title": "Como solicito acesso ao WeChat?",
            "content": "Abra um chamado com aprovação do gestor e do diretor da área.",
            "display_order": "10",
            "is_active": "true",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    with client.db_factory() as db:
        item = db.scalar(select(ProcessPost).where(ProcessPost.title.contains("WeChat")))
        assert item
        item_id = item.id
        assert db.scalar(select(AuditLog).where(AuditLog.action == "processes.created"))

    home = client.get("/")
    assert "Acessos e solicitações" in home.text
    assert "Como solicito acesso ao WeChat?" in home.text
    assert "data-process-tab" in home.text
    assert 'class="home-support-layout"' in home.text
    assert '<aside class="process-library"' in home.text
    assert 'aria-orientation="vertical"' in home.text
    assert home.text.index('<aside class="process-library"') < home.text.index('id="start-form"')

    updated = client.post(
        f"/admin/control/processes/{item_id}",
        data={
            "csrf": csrf,
            "title": "Acesso ao WeChat",
            "content": "Aprovação atualizada.",
            "display_order": "20",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303
    assert "Acesso ao WeChat" not in client.get("/").text

    deleted = client.post(
        f"/admin/control/processes/{item_id}/delete",
        data={"csrf": csrf},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    with client.db_factory() as db:
        assert db.get(ProcessPost, item_id) is None
        actions = set(db.scalars(select(AuditLog.action)))
        assert {"processes.updated", "processes.deleted"}.issubset(actions)


def test_non_master_cannot_manage_process_posts(client):
    password = "Temporary-password-2026"
    with client.db_factory() as db:
        AuthService(db).create_user("editor.process", password, "editor")
    login(client, "editor.process", password)
    assert client.get("/admin/control/processes").status_code == 403
    response = client.post(
        "/admin/control/processes",
        data={
            "csrf": "unused",
            "title": "Bloqueado",
            "content": "Sem permissão",
            "display_order": "1",
            "is_active": "true",
        },
    )
    assert response.status_code == 403


def test_process_tabs_have_keyboard_behavior():
    javascript = (BASE_DIR / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    stylesheet = (BASE_DIR / "app" / "static" / "css" / "processes.css").read_text(
        encoding="utf-8"
    )
    assert "initProcessTabs" in javascript
    assert "ArrowDown" in javascript
    assert "aria-selected" in javascript
    assert "form[data-confirm]" in javascript
    assert "grid-template-columns: minmax(270px, 320px) minmax(0, 1fr)" in stylesheet
    assert "position: sticky" in stylesheet
