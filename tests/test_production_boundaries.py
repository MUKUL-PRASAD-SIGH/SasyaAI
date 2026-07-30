import json

import httpx
import pytest
from app.core.config import Settings
from app.main import create_app
from app.models.advisory import Intent
from app.services.llm import GeminiProvider, LLMRequest


def test_production_mode_refuses_to_start_with_missing_live_dependencies(tmp_path):
    settings = Settings(runtime_mode="production", app_environment="production")

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY") as error:
        create_app(runtime_dir=tmp_path, settings=settings)

    message = str(error.value)
    assert "DATABASE_URL" in message
    assert "AUTH_REQUIRED=true" in message
    assert "MARKET_API_KEY" in message
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" in message


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
