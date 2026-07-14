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


def test_load_valid_json():
    graph = KnowledgeRepository().load("excel")
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

