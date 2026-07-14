def create_finished_session(client, payload, resolved=True):
    created = client.post("/api/sessions", json=payload).json()
    session_id = created["session"]["id"]
    first_node = created["session"]["current_node_id"]
    value = "no" if payload["category"] == "excel" else "slow"
    client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": first_node, "value": value},
    )
    if resolved:
        client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "resolved"})
    return session_id


def test_reports_page_has_operational_rankings(client, session_payload):
    create_finished_session(client, session_payload)
    second = {**session_payload, "user_name": "Maria", "computer_name": "PC-02", "category": "windows"}
    create_finished_session(client, second)

    response = client.get("/admin/reports")
    assert response.status_code == 200
    assert "Relatórios de atendimento" in response.text
    assert "Categorias mais acionadas" in response.text
    assert "ANÁLISE AUTOMÁTICA" in response.text
    assert "Pessoas com mais atendimentos" in response.text
    assert "PC-02" in response.text


def test_report_filters_reject_invalid_period(client):
    response = client.get("/admin/reports?date_from=2026-07-20&date_to=2026-07-01")
    assert response.status_code == 422


def test_reports_csv_export_and_formula_protection(client, session_payload):
    payload = {**session_payload, "user_name": "=DANGEROUS()"}
    create_finished_session(client, payload)
    response = client.get("/admin/reports/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "'=DANGEROUS()" in response.text


def test_report_category_filter(client, session_payload):
    create_finished_session(client, session_payload)
    response = client.get("/admin/reports?category=excel")
    assert response.status_code == 200
    assert "value=\"excel\" selected" in response.text
