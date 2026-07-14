def test_create_and_read_session(client, session_payload):
    created = client.post("/api/sessions", json=session_payload)
    assert created.status_code == 201
    body = created.json()
    assert body["session"]["category"] == "excel"
    response = client.get(f"/api/sessions/{body['session']['id']}")
    assert response.status_code == 200


def test_rejects_invalid_category(client, session_payload):
    session_payload["category"] = "invalid"
    response = client.post("/api/sessions", json=session_payload)
    assert response.status_code == 422


def test_finish_resolved_and_summary(client, session_payload):
    session_id = client.post("/api/sessions", json=session_payload).json()["session"]["id"]
    response = client.post(f"/api/sessions/{session_id}/finish", json={"status": "resolved", "feedback": "Funcionou"})
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    summary = client.get(f"/api/sessions/{session_id}/summary").json()["summary"]
    assert "RESUMO DO ATENDIMENTO" in summary and "Resolvido" in summary


def test_finish_unresolved(client, session_payload):
    session_id = client.post("/api/sessions", json=session_payload).json()["session"]["id"]
    response = client.post(f"/api/sessions/{session_id}/finish", json={"status": "unresolved"})
    assert response.status_code == 200
    assert response.json()["status"] == "unresolved"

