import pytest

from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository
from app.services.knowledge_match_service import KnowledgeMatchService, normalize_text


def test_normalization_ignores_case_accents_and_punctuation():
    assert normalize_text("NÃO Abre!") == "nao abre"


def test_strong_match_routes_to_confirmation_question():
    graph = KnowledgeRepository().load("excel")
    match = KnowledgeMatchService().match(graph, "O Excel fecha ao abrir uma planilha")

    assert match.rule_id == "excel_file_problem"
    assert match.level == "high"
    assert match.routed_node == "excel_002"
    assert graph["nodes"][match.routed_node]["type"] == "question"


def test_weak_match_keeps_default_question():
    graph = KnowledgeRepository().load("excel")
    match = KnowledgeMatchService().match(graph, "Aconteceu algo estranho hoje")

    assert match.level == "low"
    assert match.routed_node == graph["start_node"]


def test_validation_rejects_triage_rule_targeting_solution():
    graph = KnowledgeRepository().load("excel")
    graph["triage_rules"][0]["target_node"] = "excel_safe"

    with pytest.raises(KnowledgeBaseError, match="deve levar a uma pergunta"):
        KnowledgeRepository.validate(graph)


def test_api_exposes_interpretation_without_echoing_description(client, session_payload):
    description = "O Excel fecha ao abrir uma planilha <script>alert(1)</script>"
    payload = {
        **session_payload,
        "issue_type": "Falha em uma planilha",
        "initial_description": description,
    }
    response = client.post("/api/sessions", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["session"]["current_node_id"] == "excel_002"
    assert body["interpretation"]["confidence_level"] == "high"
    assert body["interpretation"]["label"] == "Falha ao abrir uma planilha"
    assert description not in response.text

    current = client.get(f"/api/sessions/{body['session']['id']}").json()
    assert current["interpretation"] == body["interpretation"]


def test_solution_carries_approved_knowledge_source(client, session_payload):
    payload = {
        **session_payload,
        "issue_type": "Falha em arquivo",
        "initial_description": "A planilha não abre",
    }
    created = client.post("/api/sessions", json=payload).json()
    response = client.post(
        f"/api/sessions/{created['session']['id']}/answer",
        json={"node_id": "excel_002", "value": "one"},
    )

    assert response.status_code == 200
    source = response.json()["node"]["knowledge_source"]
    assert source["label"] == "Base de conhecimento aprovada pela TI"
    assert source["reference"] == "KB-EXCEL-EXCEL_FILE"

    summary = client.get(f"/api/sessions/{created['session']['id']}/summary").json()["summary"]
    assert "Problema interpretado: Falha ao abrir uma planilha" in summary
