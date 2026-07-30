"""Typed agent registry and safe execution telemetry helpers.

The registry makes the orchestration graph visible without pretending that
every stage needs an LLM. Reasoning agents use Gemini in production; tool and
safety agents remain deterministic or source-backed.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Literal

from app.models.advisory import AgentDescriptor, AgentRun

AGENT_REGISTRY = (
    AgentDescriptor(
        agent_id="root_manager",
        name="Root Manager",
        role="Consent-gated session owner and task-graph coordinator",
        kind="manager",
        responsibilities=[
            "Validate request context",
            "Delegate to the minimum specialist set",
            "Enforce time and safety budgets",
        ],
    ),
    AgentDescriptor(
        agent_id="intent_router",
        name="Intent Router",
        role="Classifies the request and emits a typed execution plan",
        kind="reasoning",
        production_model="gemini",
        responsibilities=[
            "Route crop, pest, and scheme questions",
            "Select knowledge collections",
            "Declare required live tools",
        ],
    ),
    AgentDescriptor(
        agent_id="crop_planning_agent",
        name="Crop Planning Agent",
        role="Produces grounded crop and resource-planning drafts",
        kind="reasoning",
        production_model="gemini",
        responsibilities=[
            "Compare reviewed crop evidence",
            "Respect farm water and budget context",
            "Explain trade-offs in the farmer's language",
        ],
    ),
    AgentDescriptor(
        agent_id="pest_diagnosis_agent",
        name="Pest Diagnosis Agent",
        role="Produces cautious IPM observations and escalation guidance",
        kind="reasoning",
        production_model="gemini",
        responsibilities=[
            "Use crop-and-region evidence",
            "Avoid unverified pesticide prescriptions",
            "Escalate image-free or uncertain diagnosis",
        ],
    ),
    AgentDescriptor(
        agent_id="scheme_navigation_agent",
        name="Scheme Navigation Agent",
        role="Explains scheme evidence and official verification steps",
        kind="reasoning",
        production_model="gemini",
        responsibilities=[
            "Match farmer context to reviewed scheme sources",
            "Surface source dates and official next steps",
            "Never claim final eligibility",
        ],
    ),
    AgentDescriptor(
        agent_id="live_data_agent",
        name="Live Data Agent",
        role="Reads AgriStack, weather, and market gateways with provenance",
        kind="tool",
        responsibilities=[
            "Refresh authorised farmer context",
            "Fetch current weather and market signals",
            "Fail closed on stale or unavailable sources",
        ],
    ),
    AgentDescriptor(
        agent_id="memory_agent",
        name="Memory Agent",
        role="Sole owner of PostgreSQL and Qdrant reads and writes",
        kind="tool",
        responsibilities=[
            "Retrieve filtered agronomy evidence",
            "Persist advisory episodes",
            "Enforce farmer-scoped memory access",
        ],
        can_write_memory=True,
    ),
    AgentDescriptor(
        agent_id="reflection_agent",
        name="Reflection Agent",
        role="Checks grounding, completeness, clarity, and escalation needs",
        kind="reasoning",
        production_model="gemini",
        responsibilities=[
            "Check evidence references",
            "Flag unsupported assumptions",
            "Request one bounded revision",
        ],
    ),
    AgentDescriptor(
        agent_id="safety_verifier",
        name="Safety Verifier",
        role="Deterministic, non-LLM delivery gate",
        kind="safety",
        responsibilities=[
            "Block ungrounded citations",
            "Apply weather and dose policy",
            "Route failed checks to human review",
        ],
    ),
)

_REGISTRY_BY_ID = {agent.agent_id: agent for agent in AGENT_REGISTRY}


def agent_descriptors(model_name: str | None = None) -> list[AgentDescriptor]:
    """Return a copy with the deployment's configured model label."""

    descriptors: list[AgentDescriptor] = []
    for descriptor in AGENT_REGISTRY:
        descriptors.append(
            descriptor.model_copy(
                update={
                    "production_model": (
                        model_name
                        if model_name and descriptor.production_model == "gemini"
                        else descriptor.production_model
                    )
                }
            )
        )
    return descriptors


@dataclass
class AgentTimer:
    """Records latency and a bounded summary for a single agent stage."""

    agent_id: str
    execution_mode: Literal["llm", "deterministic", "tool"]
    model: str | None = None

    def __post_init__(self) -> None:
        self._started_at = perf_counter()

    def finish(
        self,
        *,
        summary: str,
        input_sources: list[str] | None = None,
        confidence: float | None = None,
        status: Literal["completed", "failed", "skipped"] = "completed",
    ) -> AgentRun:
        descriptor = _REGISTRY_BY_ID[self.agent_id]
        return AgentRun(
            agent_id=descriptor.agent_id,
            name=descriptor.name,
            role=descriptor.role,
            status=status,
            execution_mode=self.execution_mode,
            duration_ms=max(0, round((perf_counter() - self._started_at) * 1_000)),
            summary=summary,
            model=self.model,
            input_sources=input_sources or [],
            output_confidence=confidence,
        )
