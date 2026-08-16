import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from shutil import copytree

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.integration import ConsentScope
from app.services.consent import ConsentAdapterUnavailableError, SyntheticConsentAdapter
from app.services.memory import SeedDataError, SeedRepository


def client_for(tmp_path):
    return TestClient(create_app(runtime_dir=tmp_path))


def secured_settings(*, rate_limit_requests: int = 120) -> tuple[Settings, dict[str, str]]:
    credentials = [
        {
            "api_key": "farmer-demo-key-0123456789abcdef",
            "subject": "farmer-asha",
            "roles": ["farmer"],
            "allowed_farmer_ids": ["AGR_MH_001234"],
        },
        {
            "api_key": "officer-demo-key-0123456789abcdef",
            "subject": "officer-kulkarni",
            "roles": ["extension_officer"],
            "allowed_farmer_ids": ["AGR_MH_001234"],
        },
        {
            "api_key": "admin-demo-key-0123456789abcdef0",
            "subject": "security-admin",
            "roles": ["system_admin"],
        },
    ]
    settings = Settings(
        auth_required=True,
        auth_principals_json=json.dumps(credentials),
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=60,
    )
    return settings, {
        "farmer": credentials[0]["api_key"],
        "officer": credentials[1]["api_key"],
        "admin": credentials[2]["api_key"],
    }


def test_health_check(tmp_path):
    response = client_for(tmp_path).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_origins_are_allowed_for_post_requests(tmp_path):
    response = client_for(tmp_path).options(
        "/api/v1/query",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


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


def test_hard_safety_failure_can_only_be_rejected_in_the_hitl_queue(tmp_path):
    client = client_for(tmp_path)
    query_response = client.post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "What should I do about aphids?",
            "requested_dose_ml_per_l": 3,
        },
    )
    case_id = query_response.json()["hitl_case_id"]

    approve_response = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={"decision": "approve", "reviewer_note": "Approve the draft."},
    )
    edit_response = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={
            "decision": "edit_and_approve",
            "reviewer_note": "Use a revised dose.",
            "edited_recommendation": "Use 1 ml/L.",
        },
    )
    queued_case = next(case for case in client.get("/api/v1/hitl").json() if case["case_id"] == case_id)

    assert approve_response.status_code == 409
    assert edit_response.status_code == 409
    assert approve_response.json()["detail"] == (
        "This case has failed hard safety checks and cannot be approved in the local demonstrator."
    )
    assert queued_case["status"] == "pending"
    assert queued_case["decision_history"] == []

    reject_response = client.post(
        f"/api/v1/hitl/{case_id}/decision",
        json={"decision": "reject", "reviewer_note": "Dose exceeds the verified protocol."},
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert len(reject_response.json()["decision_history"]) == 1


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


def test_simultaneous_hitl_decisions_allow_exactly_one_transition(tmp_path):
    app = create_app(runtime_dir=tmp_path)
    query_response = TestClient(app).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "There are spots on my cotton leaves.",
        },
    )
    case_id = query_response.json()["hitl_case_id"]

    def decide(note: str) -> int:
        response = TestClient(app).post(
            f"/api/v1/hitl/{case_id}/decision",
            json={"decision": "approve", "reviewer_note": note},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(decide, ["First reviewer", "Second reviewer"]))

    queue_response = TestClient(app).get("/api/v1/hitl")
    case = next(item for item in queue_response.json() if item["case_id"] == case_id)
    assert sorted(statuses) == [200, 409]
    assert case["status"] == "approved"
    assert len(case["decision_history"]) == 1


def test_query_and_farmer_context_require_advisory_consent(tmp_path, monkeypatch):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    consent = deepcopy(service.repository.get_consent("AGR_MH_001234"))
    consent["advisory"] = False
    profile_reads: list[str] = []

    monkeypatch.setattr(service.repository, "get_consent", lambda _farmer_id: consent)

    def profile_read_should_not_happen(farmer_id: str):
        profile_reads.append(farmer_id)
        raise AssertionError("Profile reads must follow granted consent only.")

    monkeypatch.setattr(service.repository, "get_farmer", profile_read_should_not_happen)
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
    assert profile_reads == []


@pytest.mark.parametrize(
    "consent_changes",
    [
        {"status": "denied"},
        {"status": "revoked", "revoked_at": "2026-07-15T00:00:00Z"},
        {"expires_at": "2020-01-01T00:00:00Z"},
        {"scopes": ["farmer_profile"]},
    ],
    ids=["denied", "revoked", "expired", "missing-advisory-scope"],
)
def test_non_granted_consent_blocks_every_protected_route_before_profile_access(
    tmp_path, monkeypatch, consent_changes
):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    consent = deepcopy(service.repository.get_consent("AGR_MH_001234"))
    consent.update(consent_changes)
    profile_reads: list[str] = []

    monkeypatch.setattr(service.repository, "get_consent", lambda _farmer_id: consent)

    def profile_read_should_not_happen(farmer_id: str):
        profile_reads.append(farmer_id)
        raise AssertionError("A denied preflight must not access a farmer profile.")

    monkeypatch.setattr(service.repository, "get_farmer", profile_read_should_not_happen)
    client = TestClient(app)

    responses = [
        client.post(
            "/api/v1/query",
            json={
                "farmer_id": "AGR_MH_001234",
                "query": "Should I switch from cotton to soybean?",
            },
        ),
        client.get("/api/v1/farmers/AGR_MH_001234"),
        client.post(
            "/api/v1/memory/search",
            json={"farmer_id": "AGR_MH_001234", "query": "cotton"},
        ),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403]
    assert profile_reads == []


def test_preflight_precedes_authorised_profile_read_and_exposes_fixture_provenance(
    tmp_path, monkeypatch
):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    client = TestClient(app)
    calls: list[str] = []
    real_preflight = service.consent_adapter.preflight
    real_profile_read = service.repository.get_farmer

    def tracked_preflight(**kwargs):
        calls.append("preflight")
        return real_preflight(**kwargs)

    def tracked_profile_read(farmer_id: str):
        calls.append("profile")
        return real_profile_read(farmer_id)

    monkeypatch.setattr(service.consent_adapter, "preflight", tracked_preflight)
    monkeypatch.setattr(service.repository, "get_farmer", tracked_profile_read)
    response = client.post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
        },
    )

    adapter = SyntheticConsentAdapter(
        service.repository,
        clock=lambda: datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    result = adapter.preflight(
        farmer_id="AGR_MH_001234",
        purpose="agricultural_advisory",
        required_scopes=frozenset({ConsentScope.ADVISORY}),
        request_id="test-request",
    )

    assert response.status_code == 200
    assert calls[:2] == ["preflight", "profile"]
    assert result is not None and result.allowed is True
    assert result.consent.provenance.provider == "synthetic_seed"
    assert result.consent.provenance.source_record_id == "SYN_CONSENT_MH_001234"
    assert result.consent.provenance.retrieved_at == datetime(2026, 7, 30, tzinfo=timezone.utc)


def test_unknown_farmer_returns_not_found_without_a_profile_read(tmp_path, monkeypatch):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    profile_reads: list[str] = []

    def profile_read_should_not_happen(farmer_id: str):
        profile_reads.append(farmer_id)
        raise AssertionError("Unknown farmer must be handled by consent preflight.")

    monkeypatch.setattr(service.repository, "get_farmer", profile_read_should_not_happen)
    client = TestClient(app)

    responses = [
        client.post(
            "/api/v1/query",
            json={"farmer_id": "AGR_UNKNOWN", "query": "What should I plant?"},
        ),
        client.get("/api/v1/farmers/AGR_UNKNOWN"),
        client.post(
            "/api/v1/memory/search",
            json={"farmer_id": "AGR_UNKNOWN", "query": "plant"},
        ),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]
    assert profile_reads == []


def test_granted_consent_with_missing_profile_fails_closed_without_writing_runtime_state(
    tmp_path, monkeypatch
):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    monkeypatch.setattr(service.repository, "get_farmer", lambda _farmer_id: None)

    response = TestClient(app).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Consent-gated data access is unavailable; no advisory was delivered."
    )
    assert not (tmp_path / "farmer_memory.json").exists()
    assert not (tmp_path / "hitl_queue.json").exists()


def test_unavailable_consent_adapter_fails_closed_before_profile_access(tmp_path, monkeypatch):
    app = create_app(runtime_dir=tmp_path)
    service = app.state.advisory_service
    profile_reads: list[str] = []

    class UnavailableAdapter:
        def preflight(self, **_kwargs):
            raise ConsentAdapterUnavailableError("Injected adapter outage.")

    def profile_read_should_not_happen(farmer_id: str):
        profile_reads.append(farmer_id)
        raise AssertionError("Unavailable preflight must not access a farmer profile.")

    service.consent_adapter = UnavailableAdapter()
    monkeypatch.setattr(service.repository, "get_farmer", profile_read_should_not_happen)

    response = TestClient(app).post(
        "/api/v1/query",
        json={"farmer_id": "AGR_MH_001234", "query": "What should I plant?"},
    )

    assert response.status_code == 503
    assert profile_reads == []


def test_invalid_seed_data_fails_fast_at_repository_initialization(tmp_path):
    source_seed_dir = Path(__file__).resolve().parents[1] / "data" / "seed"
    seed_dir = tmp_path / "seed"
    copytree(source_seed_dir, seed_dir)
    farmer_path = seed_dir / "farmers" / "AGR_MH_001234.json"
    farmer = json.loads(farmer_path.read_text(encoding="utf-8"))
    farmer.pop("synthetic_data")
    farmer_path.write_text(json.dumps(farmer), encoding="utf-8")

    with pytest.raises(SeedDataError, match="Invalid farmer"):
        SeedRepository(seed_dir)


def test_corrupt_local_memory_fails_closed_without_delivering_advice(tmp_path):
    (tmp_path / "farmer_memory.json").write_text("{broken", encoding="utf-8")

    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Local demonstrator state is unavailable; no advisory was delivered."


def test_corrupt_hitl_queue_returns_a_controlled_service_error(tmp_path):
    (tmp_path / "hitl_queue.json").write_text("{broken", encoding="utf-8")

    response = client_for(tmp_path).get("/api/v1/hitl")

    assert response.status_code == 503
    assert response.json()["detail"] == "Local demonstrator state is unavailable; no advisory was delivered."


def test_unknown_farmer_is_not_found(tmp_path):
    response = client_for(tmp_path).get("/api/v1/farmers/AGR_UNKNOWN")

    assert response.status_code == 404


def test_farmer_registration_returns_session_token(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/farmers/register",
        json={
            "name": "Test Farmer",
            "email": "test.farmer@demo.sasyaai.local",
            "state": "Maharashtra",
            "district": "Pune",
            "season": "kharif",
            "current_crop": "soybean",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["access_token"]
    assert body["roles"] == ["farmer"]
    assert body["farmer"]["farmer_id"].startswith("AGR_")


def test_registered_farmer_session_can_query_without_api_key(tmp_path):
    settings, _keys = secured_settings()
    client = TestClient(create_app(runtime_dir=tmp_path, settings=settings))

    register = client.post(
        "/api/v1/farmers/register",
        json={
            "name": "Session Farmer",
            "email": "session.farmer@demo.sasyaai.local",
            "state": "Maharashtra",
            "district": "Pune",
            "season": "kharif",
            "current_crop": "soybean",
        },
    )
    assert register.status_code == 200
    token = register.json()["access_token"]
    farmer_id = register.json()["farmer"]["farmer_id"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    query = client.post(
        "/api/v1/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "farmer_id": farmer_id,
            "query": "Should I irrigate soybean this week?",
            "language": "en",
        },
    )
    unauthenticated = client.post(
        "/api/v1/query",
        json={
            "farmer_id": farmer_id,
            "query": "Should I irrigate soybean this week?",
            "language": "en",
        },
    )

    assert me.status_code == 200
    assert me.json()["subject"] == f"farmer:{farmer_id}"
    assert query.status_code == 200
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"] == "Authentication is required for this endpoint."
    assert (tmp_path / "registered_farmers.json").exists()
    stored = json.loads((tmp_path / "registered_farmers.json").read_text(encoding="utf-8"))
    assert any(item["farmer_id"] == farmer_id for item in stored)


def test_registered_farmer_can_relogin_with_email_otp(tmp_path):
    settings, _keys = secured_settings()
    # Synthetic-style settings so demo OTP codes are exposed even when not "development".
    settings = settings.model_copy(
        update={"app_environment": "production", "production_data_mode": "synthetic"}
    )
    client = TestClient(create_app(runtime_dir=tmp_path, settings=settings))

    register = client.post(
        "/api/v1/farmers/register",
        json={
            "name": "OTP Farmer",
            "email": "otp.farmer@demo.sasyaai.local",
            "state": "Maharashtra",
            "district": "Nagpur",
            "season": "kharif",
            "current_crop": "cotton",
        },
    )
    assert register.status_code == 200
    farmer_id = register.json()["farmer"]["farmer_id"]

    challenge = client.post(
        "/api/v1/auth/login",
        json={
            "role": "farmer",
            "auth_method": "email_otp",
            "email": "otp.farmer@demo.sasyaai.local",
        },
    )
    assert challenge.status_code == 200
    otp_code = challenge.json()["otp_demo_code"]
    assert otp_code

    login = client.post(
        "/api/v1/auth/login",
        json={
            "role": "farmer",
            "auth_method": "email_otp",
            "email": "otp.farmer@demo.sasyaai.local",
            "otp_code": otp_code,
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert token
    assert login.json()["allowed_farmer_ids"] == [farmer_id]

    me = client.get("/api/v1/auth/me", headers={"X-API-Key": token})
    assert me.status_code == 200
    assert me.json()["roles"] == ["farmer"]


def test_google_login_requires_registered_farmer(tmp_path):
    settings, _keys = secured_settings()
    client = TestClient(create_app(runtime_dir=tmp_path, settings=settings))

    unknown = client.post(
        "/api/v1/auth/google/demo",
        json={"email": "unknown.farmer@gmail.com"},
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Farmer not registered. Please register first."

    register = client.post(
        "/api/v1/farmers/register",
        json={
            "name": "Google Farmer",
            "email": "google.farmer@gmail.com",
            "state": "Maharashtra",
            "district": "Pune",
            "season": "kharif",
            "current_crop": "soybean",
        },
    )
    assert register.status_code == 200
    farmer_id = register.json()["farmer"]["farmer_id"]

    response = client.post(
        "/api/v1/auth/google/demo",
        json={"email": "google.farmer@gmail.com"},
    )
    assert response.status_code == 200
    body = response.json()
    token = body["access_token"]
    assert body["roles"] == ["farmer"]
    assert body["allowed_farmer_ids"] == [farmer_id]
    assert token
    assert "demo" not in (body.get("message") or "").lower()

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["subject"] == f"farmer:{farmer_id}"


def test_unregistered_farmer_email_otp_is_rejected(tmp_path):
    settings, _keys = secured_settings()
    client = TestClient(create_app(runtime_dir=tmp_path, settings=settings))

    challenge = client.post(
        "/api/v1/auth/login",
        json={
            "role": "farmer",
            "auth_method": "email_otp",
            "email": "not.registered@gmail.com",
        },
    )
    assert challenge.status_code == 404
    assert challenge.json()["detail"] == "Farmer not registered. Please register first."
    assert not challenge.json().get("access_token")
    assert not challenge.json().get("otp_demo_code")


def test_api_key_authentication_roles_and_farmer_assignments(tmp_path):
    settings, keys = secured_settings()
    client = TestClient(create_app(runtime_dir=tmp_path, settings=settings))
    farmer_headers = {"X-API-Key": keys["farmer"]}
    officer_headers = {"X-API-Key": keys["officer"]}

    unauthenticated = client.get("/api/v1/farmers/AGR_MH_001234")
    assigned_farmer = client.get("/api/v1/farmers/AGR_MH_001234", headers=farmer_headers)
    unassigned_farmer = client.get("/api/v1/farmers/AGR_KA_009012", headers=farmer_headers)
    farmer_queue = client.get("/api/v1/hitl", headers=farmer_headers)
    officer_queue = client.get("/api/v1/hitl", headers=officer_headers)

    assert unauthenticated.status_code == 401
    assert assigned_farmer.status_code == 200
    assert unassigned_farmer.status_code == 403
    assert farmer_queue.status_code == 403
    assert officer_queue.status_code == 200


def test_protected_requests_are_rate_limited_and_audited_without_query_content(tmp_path):
    settings, keys = secured_settings(rate_limit_requests=1)
    app = create_app(runtime_dir=tmp_path, settings=settings)
    client = TestClient(app)
    farmer_headers = {"X-API-Key": keys["farmer"]}
    admin_headers = {"X-API-Key": keys["admin"]}

    first_response = client.get("/api/v1/farmers/AGR_MH_001234", headers=farmer_headers)
    throttled_response = client.get("/api/v1/farmers/AGR_MH_001234", headers=farmer_headers)
    audit_response = client.get("/api/v1/audit", headers=admin_headers)

    assert first_response.status_code == 200
    assert throttled_response.status_code == 429
    assert audit_response.status_code == 200
    audit_events = audit_response.json()
    farmer_event = next(event for event in audit_events if event["actor_subject"] == "farmer-asha")
    assert farmer_event["resource"] == "farmer:AGR_MH_001234"
    assert "Should I" not in json.dumps(farmer_event)


def test_admin_runtime_deletion_purges_local_state_and_records_external_follow_up(tmp_path):
    settings, keys = secured_settings()
    app = create_app(runtime_dir=tmp_path, settings=settings)
    client = TestClient(app)
    farmer_headers = {"X-API-Key": keys["farmer"]}
    admin_headers = {"X-API-Key": keys["admin"]}

    query_response = client.post(
        "/api/v1/query",
        headers=farmer_headers,
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
        },
    )
    deletion_response = client.delete(
        "/api/v1/farmers/AGR_MH_001234/runtime-data",
        headers=admin_headers,
    )

    assert query_response.status_code == 200
    assert deletion_response.status_code == 200
    deletion = deletion_response.json()
    assert deletion["status"] == "pending_external_cleanup"
    assert deletion["locally_purged_scopes"] == ["advisory_memory", "hitl_cases"]
    assert app.state.advisory_service.memory.search("AGR_MH_001234", "soybean") == []
    requests = json.loads((tmp_path / "deletion_requests.json").read_text(encoding="utf-8"))
    assert requests[0]["farmer_id"] == "AGR_MH_001234"


def test_local_runtime_retention_prunes_stale_advisory_memory_before_access(tmp_path):
    (tmp_path / "farmer_memory.json").write_text(
        json.dumps(
            [
                {
                    "request_id": "old-request",
                    "farmer_id": "AGR_MH_001234",
                    "intent": "crop_plan_request",
                    "query": "Old synthetic advisory",
                    "outcome": "delivered",
                    "timestamp": "2000-01-01T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )

    app = create_app(runtime_dir=tmp_path, settings=Settings(retention_days=1))
    response = TestClient(app).post(
        "/api/v1/memory/search",
        json={"farmer_id": "AGR_MH_001234", "query": "advisory"},
    )

    assert response.status_code == 200
    assert response.json() == []
