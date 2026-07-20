from app.config import BASE_DIR


def test_home_omits_removed_identification_fields(client):
    response = client.get("/")
    assert response.status_code == 200
    for field_name in ("asset_tag", "device_model", "urgency", "impact"):
        assert f'name="{field_name}"' not in response.text


def test_home_requires_all_visible_fields(client):
    response = client.get("/")
    for field_name in (
        "user_name", "department", "location", "computer_name",
        "issue_type", "initial_description", "category",
    ):
        assert f'name="{field_name}"' in response.text
    assert response.text.count(" required") >= 7


def test_completed_service_has_redirect_to_home_action():
    javascript = (BASE_DIR / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'id="close-service"' in javascript
    assert "document.querySelector('#close-service').onclick" in javascript
    assert "location.href='/'" in javascript


def test_abandonment_always_redirects_to_home(client, session_payload):
    session_id = client.post("/api/sessions", json=session_payload).json()["session"]["id"]
    response = client.post(
        f"/api/sessions/{session_id}/finish",
        json={"status": "abandoned"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "abandoned"

    javascript = (BASE_DIR / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    abandon_handler = javascript.split("document.querySelector('#leave-link').onclick", 1)[1]
    assert "finally" in abandon_handler
    assert "sessionStorage.removeItem('it-session-id')" in abandon_handler
    assert "window.location.replace('/')" in abandon_handler


def test_header_has_local_3d_scroll_trigger_and_static_navigation(client):
    page = client.get("/")
    assert page.status_code == 200
    assert 'class="topbar"' in page.text
    assert '<nav>' in page.text
    assert "brand.css?v=20260715-7" in page.text
    assert "app.js?v=20260720-1" in page.text

    javascript = (BASE_DIR / "app" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "initBrandScrollTrigger" in javascript
    assert "--text-shift-x" in javascript
    assert "querySelector('.brand')" in javascript

    stylesheet = (BASE_DIR / "app" / "static" / "css" / "brand.css").read_text(encoding="utf-8")
    assert '[data-scroll3d="active"]' in stylesheet
    assert "@keyframes logo-horizontal-spin" in stylesheet
    assert "animation: logo-horizontal-spin" in stylesheet


def test_rejects_session_with_missing_or_blank_required_fields(client, session_payload):
    for field_name in (
        "user_name", "department", "location", "computer_name",
        "issue_type", "initial_description",
    ):
        missing = {**session_payload}
        missing.pop(field_name)
        assert client.post("/api/sessions", json=missing).status_code == 422

        blank = {**session_payload, field_name: "   "}
        assert client.post("/api/sessions", json=blank).status_code == 422


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
    client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    )
    response = client.post(f"/api/sessions/{session_id}/finish", json={"status": "resolved", "feedback": "Funcionou"})
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    summary = client.get(f"/api/sessions/{session_id}/summary").json()["summary"]
    assert "RESUMO DO ATENDIMENTO" in summary and "Resolvido" in summary
    assert "Patrimônio:" not in summary
    assert "Modelo:" not in summary
    assert "Urgência:" not in summary
    assert "Impacto:" not in summary


def test_finish_unresolved(client, session_payload):
    session_id = client.post("/api/sessions", json=session_payload).json()["session"]["id"]
    client.post(
        f"/api/sessions/{session_id}/answer",
        json={"node_id": "excel_001", "value": "no"},
    )
    client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"})
    client.post(f"/api/sessions/{session_id}/solution-result", json={"result": "unresolved"})
    response = client.post(f"/api/sessions/{session_id}/finish", json={"status": "unresolved"})
    assert response.status_code == 200
    assert response.json()["status"] == "unresolved"


def test_cannot_finish_before_trying_available_solutions(client, session_payload):
    session_id = client.post("/api/sessions", json=session_payload).json()["session"]["id"]
    response = client.post(f"/api/sessions/{session_id}/finish", json={"status": "unresolved"})
    assert response.status_code == 422
    assert "orientação" in response.json()["detail"]
