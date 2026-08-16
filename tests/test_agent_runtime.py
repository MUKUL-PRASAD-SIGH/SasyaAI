import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from scripts.ingest_reviewed_corpus import validated_documents


def client_for(tmp_path) -> TestClient:
    return TestClient(create_app(runtime_dir=tmp_path))


def test_agent_registry_exposes_bounded_roles_and_one_memory_writer(tmp_path):
    response = client_for(tmp_path).get("/api/v1/agents")

    assert response.status_code == 200
    agents = response.json()
    assert len(agents) == 9
    assert {agent["agent_id"] for agent in agents} >= {
        "root_manager",
        "intent_router",
        "reflection_agent",
        "safety_verifier",
    }
    assert [agent["agent_id"] for agent in agents if agent["can_write_memory"]] == [
        "memory_agent"
    ]
    assert next(agent for agent in agents if agent["agent_id"] == "safety_verifier")[
        "production_model"
    ] is None


def test_advisory_returns_safe_agent_execution_telemetry(tmp_path):
    response = client_for(tmp_path).post(
        "/api/v1/query",
        json={
            "farmer_id": "AGR_MH_001234",
            "query": "Should I switch from cotton to soybean?",
            "intent": "crop_plan_request",
        },
    )

    assert response.status_code == 200
    runs = response.json()["agent_runs"]
    assert runs[0]["agent_id"] == "root_manager"
    assert {run["agent_id"] for run in runs} >= {
        "intent_router",
        "crop_planning_agent",
        "memory_agent",
        "reflection_agent",
        "safety_verifier",
    }
    assert all(run["duration_ms"] >= 0 for run in runs)
    assert all("chain" not in run["summary"].lower() for run in runs)
    assert next(run for run in runs if run["agent_id"] == "safety_verifier")[
        "execution_mode"
    ] == "deterministic"


def test_evaluation_corpus_has_expected_coverage_and_provenance(tmp_path):
    client = client_for(tmp_path)
    stats_response = client.get("/api/v1/knowledge/stats")
    farmers_response = client.get("/api/v1/demo/farmers")

    assert stats_response.status_code == 200
    assert stats_response.json() == {
        "runtime_mode": "demo",
        "collections": {"crop_kb": 54, "pest_kb": 36, "scheme_kb": 15},
        "total_documents": 105,
        "regions": 18,
        "crops": 20,
    }
    assert farmers_response.status_code == 200
    assert len(farmers_response.json()) == 18
    assert len({farmer["state"] for farmer in farmers_response.json()}) == 18

    seed_root = Path(__file__).resolve().parents[1] / "data" / "seed" / "kb"
    for filename in ("crops.json", "pests.json", "schemes.json"):
        records = json.loads((seed_root / filename).read_text(encoding="utf-8"))
        assert records
        assert all(record["review_status"] == "synthetic_reference" for record in records)
        assert all(record["source_url"].startswith("https://") for record in records)
        assert all(record["source_updated_at"] for record in records)


def test_bulk_ingest_validator_generates_stable_document_ids(tmp_path):
    source = tmp_path / "reviewed.jsonl"
    record = {
        "collection": "crop_kb",
        "title": "Reviewed soybean planning note",
        "content": "Reviewer-approved content with enough detail for governed retrieval.",
        "state": "Maharashtra",
        "source_name": "Official extension publication",
        "source_url": "https://example.gov.in/soybean",
        "source_updated_at": "2026-07-01T00:00:00Z",
        "reviewed_by": "Agronomy review board",
        "metadata": {"crop": "soybean"},
    }
    source.write_text(json.dumps(record) + "\n", encoding="utf-8")

    first = list(validated_documents(source))[0]
    second = list(validated_documents(source))[0]

    assert first.document_id == second.document_id
    assert first.document_id.startswith("sha256:")
