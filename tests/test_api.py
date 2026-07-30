from copy import deepcopy

from app.main import create_app
from fastapi.testclient import TestClient


def client_for(tmp_path):
    return TestClient(create_app(runtime_dir=tmp_path))


def test_health_check(tmp_path):
    response = client_for(tmp_path).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_crop_plan_is_delivered_with_evidence(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
            "language": "mr",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["intent"] == "crop_plan_request"
    assert body["status"] == "delivered"
    assert body["confidence"] >= 0.70
    assert body["evidence"]
    assert "सोयाबीन" in body["explanation"]


def test_karnataka_crop_plan_uses_a_feasible_seeded_option(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_KA_009012",
            "query": "What should I plant this Kharif season?",
        },
    )

    body = response.json()
    water_check = next(check for check in body["verification"] if check["name"] == "water_budget")
    financial_check = next(
        check for check in body["verification"] if check["name"] == "financial_feasibility"
    )
    assert response.status_code == 200
    assert body["status"] == "delivered"
    assert "millet" in body["recommendation"].lower()
    assert "180 mm" in water_check["message"]
    assert "220 mm" in water_check["message"]
    assert financial_check["status"] == "pass"


def test_low_confidence_diagnosis_is_queued_for_review(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={"farmer_id": "AGR_MH_001234", "query": "There are spots on my cotton leaves."},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["intent"] == "diagnose"
    assert body["status"] == "requires_human_review"
    assert body["hitl_case_id"]


def test_unsafe_pesticide_dose_is_blocked(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "What should I do about aphids?",
            "requested_dose_ml_per_l": 3,
        },
    )

    body = response.json()
    pesticide_check = next(
        check for check in body["verification"] if check["name"] == "pesticide_safety"
    )
    assert response.status_code == 200
    assert body["status"] == "requires_human_review"
    assert pesticide_check["status"] == "fail"


def test_dose_without_a_matching_crop_protocol_is_blocked(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_KA_009012",
            "query": "What should I do about aphids on my maize?",
            "requested_dose_ml_per_l": 1,
        },
    )

    body = response.json()
    pesticide_check = next(
        check for check in body["verification"] if check["name"] == "pesticide_safety"
    )
    assert response.status_code == 200
    assert body["intent"] == "diagnose"
    assert body["status"] == "requires_human_review"
    assert pesticide_check["status"] == "fail"
    assert "No matching seeded crop-and-region treatment protocol" in pesticide_check["message"]


def test_hitl_case_has_review_context_and_an_immutable_decision(tmp_path):
    client = client_for(tmp_path)
    query_response = client.post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "There are spots on my cotton leaves.",
        },
    )
    case_id = query_response.json()["hitl_case_id"]

    queue_response = client.get("/api/v1/hitl")
    queued_case = next(case for case in queue_response.json() if case["case_id"] == case_id)
    assert queue_response.status_code == 200
    assert queued_case["original_recommendation"]
    assert queued_case["evidence"]
    assert queued_case["verification"]
    assert queued_case["trace"]

    incomplete_edit = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={"decision": "edit_and_approve", "reviewer_note": "Make the wording more specific."},
    )
    assert incomplete_edit.status_code == 422

    decision_response = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={
            "decision": "edit_and_approve",
            "reviewer_name": "R. Kulkarni",
            "reviewer_note": "Use the approved local IPM wording.",
            "edited_recommendation": "Inspect leaves and use only the officer-approved protocol.",
        },
    )
    decision = decision_response.json()
    assert decision_response.status_code == 200
    assert decision["status"] == "approved"
    assert decision["decision_history"] == [
        {
            "decision": "edit_and_approve",
            "reviewer_name": "R. Kulkarni",
            "reviewer_note": "Use the approved local IPM wording.",
            "edited_recommendation": "Inspect leaves and use only the officer-approved protocol.",
            "decided_at": decision["decision_history"][0]["decided_at"],
        }
    ]

    repeat_decision = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={"decision": "reject", "reviewer_note": "This must not overwrite the decision."},
    )
    assert repeat_decision.status_code == 409


def test_query_and_farmer_context_require_advisory_consent(tmp_path, monkeypatch):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    farmer = deepcopy(service.repository.get_farmer("AGR_MH_001234"))
    farmer["consent"]["advisory"] = False
    monkeypatch.setattr(service.repository, "get_farmer", lambda _farmer_id: farmer)
    client = TestClient(app)

    query_response = client.post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
        },
    )
    farmer_response = client.get("/api/v1/farmers/AGR_MH_001234")

    assert query_response.status_code == 403
    assert farmer_response.status_code == 403


def test_unknown_farmer_is_not_found(tmp_path):
    response = client_for(tmp_path).get("/api/v1/farmers/AGR_UNKNOWN")

    assert response.status_code == 404
