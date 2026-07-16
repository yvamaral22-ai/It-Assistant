import json
import re
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from app.config import BASE_DIR
from app.models import AuditLog, KnowledgeVersion, User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.auth_service import AuthService
from app.services.knowledge_version_service import KnowledgeVersionService


def csrf_from(response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match
    return match.group(1)


def login_as(client, username: str, password: str):
    page = client.get("/admin/login")
    return client.post(
        "/admin/login",
        data={"username": username, "password": password, "csrf": csrf_from(page)},
        follow_redirects=False,
    )


def test_structured_session_data_and_feedback(client, session_payload):
    payload = {
        **session_payload,
        "location": "Matriz",
        "asset_tag": "PAT-123",
        "device_model": "Notebook X",
        "issue_type": "Excel não abre",
        "urgency": "high",
        "impact": "team",
    }
    created = client.post("/api/sessions", json=payload).json()
    session_id = created["session"]["id"]
    assert created["session"]["asset_tag"] == "PAT-123"
    client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    )
    client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "resolved"})
    feedback = client.post(
        f"/api/sessions/{session_id}/feedback",
        json={"rating": 5, "feedback": "Orientação clara"},
    )
    assert feedback.status_code == 200
    saved = client.get(f"/api/sessions/{session_id}").json()["session"]
    assert saved["rating"] == 5
    assert saved["final_feedback"] == "Orientação clara"


def test_valid_knowledge_change_creates_draft_without_publishing(authenticated_client):
    page = authenticated_client.get("/admin/control/knowledge/excel")
    original = (BASE_DIR / "app" / "knowledge_base" / "excel.json").read_text(encoding="utf-8")
    response = authenticated_client.post(
        "/admin/control/knowledge/excel",
        data={"csrf": csrf_from(page), "content": original, "change_note": "Teste de rascunho"},
    )
    assert response.status_code == 200
    assert "Rascunho v" in response.text
    assert (BASE_DIR / "app" / "knowledge_base" / "excel.json").read_text(encoding="utf-8") == original
    with authenticated_client.db_factory() as db:
        versions = list(db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.category == "excel")))
        assert any(item.status == "draft" for item in versions)
        assert db.scalar(select(AuditLog).where(AuditLog.action == "knowledge.draft_created"))


def test_publish_and_restore_with_temporary_knowledge_base(client, tmp_path):
    categories = {"categories": [{"slug": "sample", "name": "Sample", "icon": "?", "description": ""}]}
    graph = {
        "category": "sample", "title": "Sample", "start_node": "q1",
        "nodes": {
            "q1": {"type": "question", "text": "Teste?", "options": [{"label": "Sim", "value": "yes", "next": "s1"}]},
            "s1": {"type": "solution", "title": "Original", "text": "Texto", "steps": ["Passo"], "ask_if_resolved": True},
        },
    }
    (tmp_path / "categories.json").write_text(json.dumps(categories), encoding="utf-8")
    (tmp_path / "sample.json").write_text(json.dumps(graph), encoding="utf-8")
    with client.db_factory() as db:
        user = AuthService(db).create_or_reset_master("master", "A-strong-local-password-2026")
        service = KnowledgeVersionService(db, KnowledgeRepository(tmp_path))
        baseline = service.ensure_baseline("sample", user)
        graph["nodes"]["s1"]["title"] = "Publicado"
        draft = service.save_draft("sample", json.dumps(graph), "Nova solução", user, "test")
        service.publish(draft, user, "test")
        assert json.loads((tmp_path / "sample.json").read_text(encoding="utf-8"))["nodes"]["s1"]["title"] == "Publicado"
        restored = service.restore_as_draft(baseline, user, "test")
        assert restored.status == "draft"
        assert "Original" in restored.content


def test_master_can_create_user_with_limited_role(authenticated_client):
    page = authenticated_client.get("/admin/control/users")
    response = authenticated_client.post(
        "/admin/control/users",
        data={
            "csrf": csrf_from(page), "username": "analista.ti",
            "password": "Temporary-password-2026", "role": "analyst",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with authenticated_client.db_factory() as db:
        user = db.scalar(select(User).where(User.username == "analista.ti"))
        assert user and user.role == "analyst"
        assert db.scalar(select(AuditLog).where(AuditLog.action == "user.created"))


def test_role_permissions_are_enforced(client):
    password = "Temporary-password-2026"
    with client.db_factory() as db:
        AuthService(db).create_user("analyst", password, "analyst")
    assert login_as(client, "analyst", password).status_code == 303
    assert client.get("/admin/reports").status_code == 200
    assert client.get("/admin/reports/export.csv").status_code == 200
    assert client.get("/admin/control/users").status_code == 403
    assert client.get("/admin/control/knowledge/excel").status_code == 403


def test_reader_cannot_export_reports(client):
    password = "Temporary-password-2026"
    with client.db_factory() as db:
        AuthService(db).create_user("reader", password, "reader")
    login_as(client, "reader", password)
    assert client.get("/admin/reports").status_code == 200
    assert client.get("/admin/reports/export.csv").status_code == 403


def test_ready_checks_database_and_knowledge(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_alembic_builds_new_database(tmp_path):
    database = tmp_path / "fresh.db"
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "head")
    from sqlalchemy import create_engine

    schema = inspect(create_engine(f"sqlite:///{database.as_posix()}"))
    assert {
        "sessions", "interactions", "users", "knowledge_versions", "audit_logs",
        "internal_notices", "process_posts",
    }.issubset(
        schema.get_table_names()
    )
    assert "service_health" not in schema.get_table_names()
    assert "rating" in {column["name"] for column in schema.get_columns("sessions")}
