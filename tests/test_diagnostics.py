import json

import pytest

from app.repositories.knowledge_repository import KnowledgeBaseError, KnowledgeRepository


def test_valid_answer(client, session_payload):
    created = client.post("/api/sessions", json=session_payload).json()
    session_id = created["session"]["id"]
    response = client.post(f"/api/sessions/{session_id}/answer", json={"node_id": "excel_001", "value": "no"})
    assert response.status_code == 200
    assert response.json()["node"]["type"] == "solution"


def test_invalid_answer(client, session_payload):
    created = client.post("/api/sessions", json=session_payload).json()
    session_id = created["session"]["id"]
    response = client.post(f"/api/sessions/{session_id}/answer", json={"node_id": "excel_001", "value": "invalid"})
    assert response.status_code == 422


def test_unresolved_tries_three_solutions_before_summary(client, session_payload):
    created = client.post("/api/sessions", json=session_payload).json()
    session_id = created["session"]["id"]
    first = client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    ).json()
    assert first["node_id"] == "excel_safe"

    second = client.post(
        f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"}
    ).json()
    assert second["status"] == "in_progress"
    assert second["node_id"] == "excel_attempt_2"

    third = client.post(
        f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"}
    ).json()
    assert third["status"] == "in_progress"
    assert third["node_id"] == "excel_attempt_3"

    finished = client.post(
        f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"}
    ).json()
    assert finished["status"] == "unresolved"
    assert finished["summary"].count("ORIENTAÇÃO APRESENTADA:") == 3


def test_back_restores_backend_question(client, session_payload):
    created = client.post("/api/sessions", json=session_payload).json()
    session_id = created["session"]["id"]
    client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    )
    previous = client.post(f"/api/sessions/{session_id}/back").json()
    assert previous["node_id"] == "excel_001"

    changed_answer = client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "yes"},
    )
    assert changed_answer.status_code == 200
    assert changed_answer.json()["node_id"] == "excel_002"


def test_load_valid_json():
    graph = KnowledgeRepository().load("excel")
    assert graph["start_node"] in graph["nodes"]


def test_all_categories_are_valid():
    repository = KnowledgeRepository()
    for category in repository.categories():
        graph = repository.load(category["slug"])
        assert graph["start_node"] in graph["nodes"]


def test_invalid_json_is_controlled(tmp_path):
    (tmp_path / "broken.json").write_text("{invalid", encoding="utf-8")
    with pytest.raises(KnowledgeBaseError):
        KnowledgeRepository(tmp_path).load("broken")


def test_missing_node_reference():
    graph = {"start_node": "a", "nodes": {"a": {"type": "question", "text": "?", "options": [{"label": "Sim", "value": "yes", "next": "missing"}]}}}
    with pytest.raises(KnowledgeBaseError, match="Destino inexistente"):
        KnowledgeRepository.validate(graph)


def test_obvious_cycle():
    graph = {"start_node": "a", "nodes": {"a": {"type": "question", "options": [{"label": "Sim", "value": "yes", "next": "a"}]}}}
    with pytest.raises(KnowledgeBaseError, match="Loop infinito"):
        KnowledgeRepository.validate(graph)
