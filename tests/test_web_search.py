from app.config import get_settings
from app.repositories.session_repository import SessionRepository
from app.services.web_search_service import WEB_NODE_ID, WebSearchService


def _reach_last_local_solution(client, session_payload):
    created = client.post("/api/sessions", json=session_payload).json()
    session_id = created["session"]["id"]
    client.post(f"/api/sessions/{session_id}/answer", json={"node_id": "excel_001", "value": "no"})
    client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"})
    client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"})
    return session_id


def test_query_removes_identity_and_preserves_error_code(client, session_payload):
    session_payload["user_name"] = "Maria Confidencial"
    session_payload["computer_name"] = "PC-SEGREDO-99"
    session_payload["issue_type"] = "Falha no HOST-FINANCEIRO-01"
    session_payload["initial_description"] = (
        "Excel não abre no PC-SEGREDO-99, contato maria@example.com, erro 0x800A03EC"
    )
    created = client.post("/api/sessions", json=session_payload).json()
    with client.db_factory() as db:
        item = SessionRepository(db).get(created["session"]["id"])
        query = WebSearchService._query(item)

    assert "excel" in query
    assert "0x800a03ec" in query
    assert "maria" not in query
    assert "segredo" not in query
    assert "financeiro" not in query


def test_web_orientation_is_rendered_inside_diagnostic(client, session_payload, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "web_search_enabled", True)
    web_node = {
        "type": "solution",
        "title": "Teste uma inicialização limpa do aplicativo",
        "text": "A fonte consultada recomenda isolar configurações locais com uma ação reversível.",
        "steps": ["Feche o Excel.", "Abra novamente e teste uma planilha vazia."],
        "ask_if_resolved": True,
        "external_research": True,
        "knowledge_source": {
            "label": "Pesquisa web interpretada pelo assistente",
            "reference": "Documentação oficial do Microsoft Excel",
        },
    }
    monkeypatch.setattr(WebSearchService, "orientation", lambda self, session: web_node)
    session_id = _reach_last_local_solution(client, session_payload)

    researched = client.post(
        f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"}
    )

    assert researched.status_code == 200
    assert researched.json()["status"] == "in_progress"
    assert researched.json()["node_id"] == WEB_NODE_ID
    assert researched.json()["node"] == web_node

    finished = client.post(
        f"/api/sessions/{session_id}/solution-result", json={"result": "resolved"}
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "resolved"
    assert "Pesquisa web interpretada" in finished.json()["summary"]


def test_web_orientation_rejects_unsafe_administrative_steps():
    steps = WebSearchService._safe_steps([
        "Abra o PowerShell como administrador.",
        "Feche o Excel e teste novamente.",
    ])

    assert steps == ["Feche o Excel e teste novamente."]
