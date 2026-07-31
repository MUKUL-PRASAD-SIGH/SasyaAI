import json

import httpx
import pytest
from app.core.config import Settings
from app.main import create_app
from app.models.advisory import Intent, KnowledgeHit
from app.services.connectors import SyntheticProductionDataGateway
from app.services.llm import AgentPlan, GeminiProvider, LLMRequest
from app.services.production import ProductionAdvisoryService
from fastembed import TextEmbedding


def test_production_mode_refuses_to_start_with_missing_live_dependencies(tmp_path):
    settings = Settings(
        runtime_mode="production",
        app_environment="production",
        production_data_mode="live",
        gemini_api_key="",
        database_url="",
        qdrant_url="",
        agristack_api_base_url="",
        agristack_access_token="",
        market_api_base_url="",
        market_api_key="",
        auth_required=False,
        auth_principals_json="",
    )

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY") as error:
        create_app(runtime_dir=tmp_path, settings=settings)

    message = str(error.value)
    assert "DATABASE_URL" in message
    assert "AUTH_REQUIRED=true" in message
    assert "MARKET_API_KEY" in message
    assert "AGRISTACK_API_BASE_URL" in message


def test_production_configuration_requires_auth_principals_when_protected():
    settings = Settings(
        runtime_mode="production",
        app_environment="production",
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://user:pass@localhost/db",
        qdrant_url="http://localhost:6333",
        agristack_api_base_url="https://gateway.example",
        agristack_access_token="test-token",
        market_api_base_url="https://market.example",
        market_api_key="test-market-key",
        auth_required=True,
        auth_principals_json="",
    )

    assert settings.production_configuration_errors() == ["AUTH_PRINCIPALS_JSON"]


def test_production_configuration_allows_local_metrics_when_otlp_is_unset():
    settings = Settings(
        runtime_mode="production",
        app_environment="production",
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://user:pass@localhost/db",
        qdrant_url="http://localhost:6333",
        agristack_api_base_url="https://gateway.example",
        agristack_access_token="test-token",
        market_api_base_url="https://market.example",
        market_api_key="test-market-key",
        auth_required=True,
        auth_principals_json='[{"api_key":"test-principal-key-1234567890","subject":"admin","roles":["system_admin"]}]',
    )

    assert settings.production_configuration_errors() == []


def test_synthetic_production_configuration_keeps_agristack_open_for_later():
    settings = Settings(
        runtime_mode="production",
        app_environment="production",
        production_data_mode="synthetic",
        gemini_api_key="test-key",
        database_url="postgresql+psycopg://user:pass@localhost/db",
        qdrant_url="http://localhost:6333",
        market_api_base_url="https://market.example",
        market_api_key="test-market-key",
        auth_required=True,
        auth_principals_json='[{"api_key":"test-principal-key-1234567890","subject":"admin","roles":["system_admin"]}]',
    )

    assert settings.production_configuration_errors() == []


def test_synthetic_production_gateway_is_explicitly_provenanced():
    gateway = SyntheticProductionDataGateway(Settings())

    consent = gateway.agristack_consent("AGR_MH_001234", "agricultural_advisory")
    context = gateway.agristack_farmer_context("AGR_MH_001234")
    weather = gateway.weather(context["data"])

    assert consent is not None
    assert context["provider"] == "synthetic_production_seed"
    assert context["freshness"] == "synthetic_reference"
    assert weather["freshness"] == "synthetic_reference"


def test_default_embedding_model_is_supported_by_cpu_only_fastembed():
    supported = {item["model"]: item for item in TextEmbedding.list_supported_models()}
    model = supported[Settings().embedding_model]

    assert model["dim"] == 384
    assert model["size_in_GB"] < 0.5
    assert "Multilingual" in model["description"]


def test_production_verifier_fails_closed_on_incomplete_required_weather():
    service = ProductionAdvisoryService.__new__(ProductionAdvisoryService)
    plan = AgentPlan(
        intent=Intent.CROP_PLAN,
        recommendation="Review the cited crop option.",
        explanation="The option is supported by the retrieved source.",
        confidence=0.81,
        evidence_ids=["crop-123"],
    )
    evidence = [
        KnowledgeHit(
            source="crop_kb",
            title="Reviewed crop option",
            score=0.88,
            metadata={"document_id": "crop-123"},
        )
    ]

    checks = service._verify(
        plan,
        evidence,
        {"provider": "open_meteo", "freshness": "live", "data": {}},
        {"provider": "not_requested", "freshness": "not_applicable", "data": {}},
        Intent.CROP_PLAN,
        needs_weather=True,
        needs_market=False,
    )

    weather = next(check for check in checks if check.name == "weather_safety")
    assert weather.status == "fail"
    assert "incomplete" in weather.message


def test_gemini_adapter_requires_typed_grounded_json_without_network_access():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == "test-key"
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "intent": "crop_plan_request",
                                            "recommendation": "Review the cited crop guidance.",
                                            "explanation": "The cited source fits the farm context.",
                                            "confidence": 0.81,
                                            "evidence_ids": ["crop-123"],
                                            "needs_human_review": False,
                                            "safety_notes": ["No dose was supplied."],
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    provider = GeminiProvider(
        Settings(gemini_api_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = provider.plan_and_draft(
        LLMRequest(
            query="What can I plant?",
            language="en",
            farmer_context={"state": "Maharashtra"},
            evidence=[{"id": "crop-123", "title": "Reviewed crop source"}],
            tool_context={"weather": {"freshness": "live"}},
        )
    )

    assert result.intent is Intent.CROP_PLAN
    assert result.evidence_ids == ["crop-123"]


def test_gemini_adapter_routes_and_reflects_through_separate_typed_calls():
    instructions: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        instruction = payload["systemInstruction"]["parts"][0]["text"]
        instructions.append(instruction)
        if "Intent Router" in instruction:
            result = {
                "intent": "diagnose",
                "specialist_agent": "pest_diagnosis_agent",
                "retrieval_collections": ["pest_kb"],
                "needs_weather": True,
                "needs_market": False,
                "route_summary": "Route the crop symptom report to cautious pest review.",
            }
        else:
            result = {
                "status": "revise",
                "notes": ["Remove unsupported treatment specificity."],
                "revised_recommendation": "Capture a clear image and seek extension review.",
                "revised_explanation": "The supplied evidence does not confirm a diagnosis.",
                "confidence_delta": -0.1,
                "needs_human_review": True,
            }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(result)}]}}
                ]
            },
        )

    provider = GeminiProvider(
        Settings(gemini_api_key="test-key"),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    request = LLMRequest(
        query="What are these spots?",
        language="en",
        farmer_context={"state": "Maharashtra", "crop": "cotton"},
        evidence=[{"id": "pest-123", "title": "Reviewed observation guide"}],
        tool_context={"weather": {"freshness": "live"}},
    )

    graph = provider.route(request)
    review = provider.reflect(
        request,
        AgentPlan.model_validate(
            {
                "intent": "diagnose",
                "recommendation": "Use a treatment.",
                "explanation": "The symptom may be a pest.",
                "confidence": 0.62,
                "evidence_ids": ["pest-123"],
                "needs_human_review": False,
                "safety_notes": [],
            }
        ),
    )

    assert graph.specialist_agent == "pest_diagnosis_agent"
    assert review.status == "revise"
    assert review.needs_human_review is True
    assert len(instructions) == 2
