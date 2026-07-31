"""Live provider-backed advisory workflow for production deployments."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import Settings
from app.models.advisory import (
    AdvisoryResponse,
    AgentRun,
    DemoFarmerSummary,
    FarmerOnboardingRequest,
    HITLCase,
    HITLDecisionRequest,
    Intent,
    KnowledgeHit,
    KnowledgeIngestRequest,
    KnowledgeStats,
    MemorySearchRequest,
    ReflectionResult,
    TraceEvent,
    VerificationCheck,
)
from app.models.integration import (
    ConsentPreflightResult,
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
    SourceProvenance,
)
from app.services.advisory import (
    AdvisoryService,
    ConsentNotGrantedError,
    FarmerNotFoundError,
    HITLCaseNotPendingError,
    HITLCaseSafetyBlockedError,
)
from app.services.agents import AgentTimer
from app.services.connectors import (
    LiveDataGateway,
    SyntheticProductionDataGateway,
    ToolDataUnavailableError,
)
from app.services.llm import AgentPlan, LLMRequest, TaskGraph, build_llm_provider
from app.services.memory import FarmerImageStore, RegisteredFarmerStore, SeedRepository
from app.services.persistence import PostgresMemoryStore
from app.services.retrieval import QdrantKnowledgeStore
from app.services.security import sanitize_user_query

_DOSE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:ml\s*/\s*l|ml/l|millilit(?:re|er)s?\s+per\s+lit(?:re|er))\b", re.I)


class ProductionAdvisoryService:
    """Coordinates live LLM, retrieval, tools, durable memory, and hard safety gates."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.memory = PostgresMemoryStore(settings.database_url)
        self.retrieval = QdrantKnowledgeStore(settings)
        self.seed_repository = (
            SeedRepository(settings.seed_data_dir)
            if settings.production_data_mode == "synthetic"
            else None
        )
        self.tools = (
            SyntheticProductionDataGateway(settings)
            if settings.production_data_mode == "synthetic"
            else LiveDataGateway(settings)
        )
        if self.seed_repository is not None:
            self.retrieval.ensure_synthetic_seed(self.seed_repository)
        self.llm = build_llm_provider(settings)
        self.registered_farmers = (
            RegisteredFarmerStore(settings.runtime_dir)
            if settings.production_data_mode == "synthetic"
            else None
        )
        self.farmer_images = (
            FarmerImageStore(settings.runtime_dir)
            if settings.production_data_mode == "synthetic"
            else None
        )

    @property
    def synthetic_data_mode(self) -> bool:
        return getattr(getattr(self, "settings", None), "production_data_mode", "live") == "synthetic"

    @staticmethod
    def _require_profile_shape(farmer_id: str, profile: dict[str, Any] | None) -> dict[str, Any]:
        if profile is None:
            raise FarmerNotFoundError(farmer_id)
        twin = profile.get("digital_twin")
        required = ("farmer_id", "state", "district", "preferred_language")
        if (
            not isinstance(profile, dict)
            or profile.get("farmer_id") != farmer_id
            or not all(isinstance(profile.get(field), str) and profile[field] for field in required)
            or not isinstance(twin, dict)
        ):
            raise ToolDataUnavailableError("The production farmer profile does not meet the trusted schema.")
        return profile

    def _registered_consent_raw(self, farmer_id: str) -> dict[str, Any] | None:
        if self.registered_farmers is None:
            return None
        farmer = self.registered_farmers.get(farmer_id)
        if farmer is None:
            return None
        consent = farmer.get("consent")
        return consent if isinstance(consent, dict) else None

    def _live_consent(
        self,
        farmer_id: str,
        required_scopes: frozenset[ConsentScope],
        *,
        request_id: str | None = None,
    ) -> ConsentPreflightResult:
        raw = self._registered_consent_raw(farmer_id) or self.tools.agristack_consent(
            farmer_id, "agricultural_advisory"
        )
        if raw is None:
            raise FarmerNotFoundError(farmer_id)
        now = datetime.now(timezone.utc)
        synthetic = self.synthetic_data_mode
        try:
            record = ConsentRecord(
                consent_id=str(raw["consent_id"]),
                farmer_id=farmer_id,
                status=raw["status"],
                purpose=str(raw["purpose"]),
                scopes=raw["scopes"],
                granted_at=raw.get("granted_at"),
                expires_at=raw.get("expires_at"),
                revoked_at=raw.get("revoked_at"),
                provenance=SourceProvenance(
                    provider=("synthetic_production_seed" if synthetic else "agristack"),
                    source_type=("synthetic_fixture" if synthetic else "live_api"),
                    source_record_id=str(raw.get("source_record_id", raw["consent_id"])),
                    retrieved_at=now,
                    data_as_of=raw.get("updated_at"),
                    freshness=("synthetic_reference" if synthetic else "live"),
                    request_id=request_id,
                ),
            )
        except (KeyError, TypeError, ValidationError) as error:
            raise ToolDataUnavailableError("The live consent provider returned an invalid receipt.") from error

        allowed = (
            record.status is ConsentStatus.GRANTED
            and record.purpose == "agricultural_advisory"
            and record.granted_at is not None
            and record.granted_at <= now
            and record.revoked_at is None
            and (record.expires_at is None or record.expires_at > now)
            and required_scopes.issubset(record.scopes)
        )
        result = ConsentPreflightResult(
            allowed=allowed,
            reason="granted" if allowed else "live_consent_not_granted",
            consent=record,
            required_scopes=required_scopes,
        )
        if not result.allowed:
            raise ConsentNotGrantedError(farmer_id)
        return result

    @staticmethod
    def _safe_farmer_context(farmer: dict[str, Any]) -> dict[str, Any]:
        """Minimise PII and pass only decision-relevant facts to the LLM."""

        twin = farmer["digital_twin"]
        allowed_twin = {
            key: twin[key]
            for key in (
                "season",
                "current_crop",
                "soil_fertility",
                "water_budget_mm",
                "budget_inr",
                "eligible_schemes",
            )
            if key in twin
        }
        return {
            "state": farmer["state"],
            "district": farmer["district"],
            "preferred_language": farmer["preferred_language"],
            "digital_twin": allowed_twin,
        }

    def _refresh_farmer_context(
        self, farmer_id: str, consent: ConsentPreflightResult
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Refresh the twin from its live authorised source before every advisory."""

        registered = (
            self.registered_farmers.get(farmer_id) if self.registered_farmers is not None else None
        )
        if registered is not None:
            profile = self._require_profile_shape(farmer_id, registered)
            self.memory.upsert_farmer(farmer_id, profile)
            self.memory.upsert_consent(farmer_id, consent.consent.model_dump(mode="json"))
            source = {
                "provider": "synthetic_production_seed",
                "source_record_id": farmer_id,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "freshness": "synthetic_reference",
                "data": profile,
            }
            return profile, source

        source = self.tools.agristack_farmer_context(farmer_id)
        profile = self._require_profile_shape(farmer_id, source.get("data"))
        self.memory.upsert_farmer(farmer_id, profile)
        self.memory.upsert_consent(farmer_id, consent.consent.model_dump(mode="json"))
        return profile, source

    @staticmethod
    def _evidence_for_prompt(hits: list[KnowledgeHit]) -> list[dict[str, Any]]:
        return [
            {
                "id": str(hit.metadata.get("document_id", hit.title)),
                "source": hit.source,
                "title": hit.title,
                "score": hit.score,
                "metadata": hit.metadata,
            }
            for hit in hits
        ]

    def _retrieve(
        self,
        farmer: dict[str, Any],
        query: str,
        collections: list[str],
    ) -> list[KnowledgeHit]:
        filters = {"state": str(farmer["state"])}
        hits: list[KnowledgeHit] = []
        for collection in collections:
            collection_filters: dict[str, str | list[str]] = filters
            if collection == "scheme_kb":
                collection_filters = {"state": [str(farmer["state"]), "all"]}
            hits.extend(
                self.retrieval.search(
                    collection,
                    query,
                    filters=collection_filters,
                    limit=3,
                )
            )
        return hits

    @staticmethod
    def _enforce_requested_intent(graph: TaskGraph, requested_intent: Intent | None) -> TaskGraph:
        """Treat an explicit API intent as a routing contract, not an LLM suggestion."""

        if requested_intent is None or graph.intent is requested_intent:
            return graph
        specialist, collection, needs_market = {
            Intent.CROP_PLAN: ("crop_planning_agent", "crop_kb", True),
            Intent.DIAGNOSE: ("pest_diagnosis_agent", "pest_kb", False),
            Intent.SCHEME: ("scheme_navigation_agent", "scheme_kb", False),
        }[requested_intent]
        return TaskGraph(
            intent=requested_intent,
            specialist_agent=specialist,
            retrieval_collections=[collection],
            needs_weather=requested_intent is not Intent.SCHEME,
            needs_market=needs_market,
            route_summary="Applied the caller's explicit typed intent.",
        )

    @staticmethod
    def _weather_is_unsafe(weather: dict[str, Any]) -> bool:
        data = weather.get("data", {})
        wind = data.get("wind_speed_kmh")
        rain_probability = data.get("max_precipitation_probability")
        return (isinstance(wind, (int, float)) and wind >= 50) or (
            isinstance(rain_probability, (int, float)) and rain_probability >= 85
        )

    @staticmethod
    def _weather_is_complete(weather: dict[str, Any]) -> bool:
        data = weather.get("data", {})
        return (
            weather.get("freshness") in {"live", "synthetic_reference"}
            and isinstance(data, dict)
            and isinstance(data.get("wind_speed_kmh"), (int, float))
            and isinstance(data.get("max_precipitation_probability"), (int, float))
        )

    def _verify(
        self,
        plan: AgentPlan,
        evidence: list[KnowledgeHit],
        weather: dict[str, Any],
        market: dict[str, Any],
        intent: Intent,
        *,
        needs_weather: bool,
        needs_market: bool,
    ) -> list[VerificationCheck]:
        evidence_ids = {str(hit.metadata.get("document_id", hit.title)) for hit in evidence}
        cited_ids = set(plan.evidence_ids)
        grounding_ok = bool(cited_ids) and cited_ids.issubset(evidence_ids)
        if not needs_weather:
            weather_check = VerificationCheck(
                name="weather_safety",
                status="not_applicable",
                message="The typed task graph did not require a weather-dependent action.",
            )
        elif not self._weather_is_complete(weather):
            weather_check = VerificationCheck(
                name="weather_safety",
                status="fail",
                message="The required live weather snapshot is incomplete and delivery is blocked.",
            )
        else:
            weather_check = VerificationCheck(
                name="weather_safety",
                status="fail" if self._weather_is_unsafe(weather) else "pass",
                message=(
                    "Live weather exceeds the configured wind/rain safety threshold."
                    if self._weather_is_unsafe(weather)
                    else "Live weather is below the configured wind/rain safety threshold."
                ),
            )
        required_snapshots = [weather] if needs_weather else []
        if needs_market:
            required_snapshots.append(market)
        accepted_freshness = {"live"}
        if self.synthetic_data_mode:
            accepted_freshness.add("synthetic_reference")
        freshness_ok = all(
            snapshot.get("freshness") in accepted_freshness
            for snapshot in required_snapshots
        )
        checks = [
            VerificationCheck(
                name="evidence_grounding",
                status="pass" if grounding_ok else "fail",
                message=(
                    "Every LLM citation maps to evidence retrieved for this request."
                    if grounding_ok
                    else "The LLM draft has missing or unverified evidence citations and is blocked."
                ),
            ),
            weather_check,
            VerificationCheck(
                name="source_freshness",
                status="pass" if freshness_ok else "fail",
                message=(
                    "Every live connector required by the typed task graph returned a current snapshot."
                    if freshness_ok
                    else "A required live connector did not return a current snapshot."
                ),
            ),
        ]
        has_dose = bool(_DOSE_PATTERN.search(f"{plan.recommendation}\n{plan.explanation}"))
        checks.append(
            VerificationCheck(
                name="pesticide_safety",
                status="fail" if has_dose else "not_applicable",
                message=(
                    "The LLM draft contains a pesticide dose and is blocked from delivery."
                    if has_dose
                    else "No LLM-supplied pesticide dose was detected; dosage needs an authorised protocol."
                ),
            )
        )
        if intent is Intent.SCHEME:
            checks.append(
                VerificationCheck(
                    name="scheme_eligibility",
                    status="not_applicable",
                    message="Eligibility must be confirmed by the authorised scheme system before submission.",
                )
            )
        if self.synthetic_data_mode:
            checks.append(
                VerificationCheck(
                    name="synthetic_data_boundary",
                    status="pass",
                    message=(
                        "This production run uses labelled synthetic farmer, consent, and "
                        "market data. It is suitable for internal workflow testing only; "
                        "switch PRODUCTION_DATA_MODE=live before serving real farmers."
                    ),
                )
            )
        return checks

    @staticmethod
    def _hitl_case(
        *,
        case_id: str,
        request_id: str,
        farmer_id: str,
        plan: AgentPlan,
        intent: Intent,
        verification: list[VerificationCheck],
        evidence: list[KnowledgeHit],
        trace: list[TraceEvent],
        agent_runs: list[AgentRun],
        reason: str,
        safety_rule_set_version: str,
    ) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "farmer_id": farmer_id,
            "status": "pending",
            "reason": reason,
            "request_id": request_id,
            "safety_rule_set_version": safety_rule_set_version,
            "intent": intent.value,
            "confidence": plan.confidence,
            "original_recommendation": plan.recommendation,
            "original_explanation": plan.explanation,
            "evidence": [hit.model_dump(mode="json") for hit in evidence],
            "verification": [check.model_dump(mode="json") for check in verification],
            "trace": [event.model_dump(mode="json") for event in trace],
            "agent_runs": [run.model_dump(mode="json") for run in agent_runs],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "decision_history": [],
        }

    def query(self, request) -> AdvisoryResponse:
        root_timer = AgentTimer(
            "root_manager", execution_mode="deterministic"
        )
        agent_runs: list[AgentRun] = []
        request_id = str(uuid4())
        cleaned_query = sanitize_user_query(request.query)
        image_context: dict[str, Any] | None = None
        image_detail = "No crop image was attached to this request."
        if request.image_id:
            if self.farmer_images is None:
                raise ToolDataUnavailableError(
                    "Image attachments are available only in synthetic production mode."
                )
            image_context = self.farmer_images.get(request.image_id)
            if image_context is None or image_context.get("farmer_id") != request.farmer_id:
                raise FarmerNotFoundError(request.farmer_id)
            image_detail = f"Attached image {request.image_id} analysed for crop symptoms."
            analysis = str(image_context.get("analysis_summary", "")).strip()
            if analysis:
                cleaned_query = sanitize_user_query(
                    f"{cleaned_query}\n\nUploaded crop image analysis: {analysis}"
                )
        request = request.model_copy(update={"query": cleaned_query})
        consent = self._live_consent(
            request.farmer_id,
            frozenset({ConsentScope.FARMER_PROFILE, ConsentScope.ADVISORY, ConsentScope.ADVISORY_MEMORY}),
            request_id=request_id,
        )
        farmer, agristack = self._refresh_farmer_context(request.farmer_id, consent)
        safe_farmer_context = self._safe_farmer_context(farmer)
        source_provenance = {
            key: agristack[key]
            for key in ("provider", "source_record_id", "retrieved_at", "freshness")
        }

        router_timer = AgentTimer(
            "intent_router", execution_mode="llm", model=self.settings.gemini_model
        )
        route_request = LLMRequest(
            query=request.query,
            language=request.language,
            farmer_context=safe_farmer_context,
            evidence=[],
            tool_context={"agristack_context_provenance": source_provenance},
            requested_intent=request.intent,
        )
        graph = self._enforce_requested_intent(self.llm.route(route_request), request.intent)
        agent_runs.append(
            router_timer.finish(
                summary=graph.route_summary,
                input_sources=["farmer_context", "query"],
            )
        )

        live_timer = AgentTimer("live_data_agent", execution_mode="tool")
        weather = (
            self.tools.weather(farmer)
            if graph.needs_weather
            else {"provider": "not_requested", "freshness": "not_applicable", "data": {}}
        )
        market = (
            self.tools.market(farmer, request.query)
            if graph.needs_market
            else {"provider": "not_requested", "freshness": "not_applicable", "data": {}}
        )
        live_sources = ["agristack"]
        if graph.needs_weather:
            live_sources.append("open_meteo")
        if graph.needs_market:
            live_sources.append("market_provider")
        agent_runs.append(
            live_timer.finish(
                summary="Fetched the live signals declared by the typed task graph.",
                input_sources=live_sources,
            )
        )

        memory_timer = AgentTimer("memory_agent", execution_mode="tool")
        evidence = self._retrieve(
            farmer,
            request.query,
            list(graph.retrieval_collections),
        )
        agent_runs.append(
            memory_timer.finish(
                summary=f"Retrieved {len(evidence)} state-filtered evidence records.",
                input_sources=list(graph.retrieval_collections),
            )
        )

        specialist_timer = AgentTimer(
            graph.specialist_agent,
            execution_mode="llm",
            model=self.settings.gemini_model,
        )
        specialist_request = LLMRequest(
            query=request.query,
            language=request.language,
            farmer_context=safe_farmer_context,
            evidence=self._evidence_for_prompt(evidence),
            tool_context={
                "weather": weather,
                "market": market,
                "agristack_context_provenance": source_provenance,
            },
            requested_intent=graph.intent,
        )
        plan = self.llm.plan_and_draft(specialist_request)
        if plan.intent is not graph.intent:
            plan = plan.model_copy(update={"intent": graph.intent, "needs_human_review": True})
        agent_runs.append(
            specialist_timer.finish(
                summary="Produced a typed farmer-facing draft grounded in retrieved evidence.",
                input_sources=[*graph.retrieval_collections, *live_sources],
                confidence=plan.confidence,
            )
        )

        reflection_timer = AgentTimer(
            "reflection_agent",
            execution_mode="llm",
            model=self.settings.gemini_model,
        )
        reflection = self.llm.reflect(specialist_request, plan)
        if reflection.status == "revise":
            plan = plan.model_copy(
                update={
                    "recommendation": (
                        reflection.revised_recommendation or plan.recommendation
                    ),
                    "explanation": reflection.revised_explanation or plan.explanation,
                    "confidence": max(
                        0.0, min(1.0, plan.confidence + reflection.confidence_delta)
                    ),
                    "needs_human_review": (
                        plan.needs_human_review or reflection.needs_human_review
                    ),
                }
            )
        elif reflection.needs_human_review:
            plan = plan.model_copy(update={"needs_human_review": True})
        agent_runs.append(
            reflection_timer.finish(
                summary=(
                    "Revised the draft within the retrieved evidence boundary."
                    if reflection.status == "revise"
                    else "Draft passed the bounded grounding and clarity review."
                ),
                input_sources=["specialist_draft", "retrieved_evidence"],
                confidence=plan.confidence,
            )
        )

        verifier_timer = AgentTimer("safety_verifier", execution_mode="deterministic")
        verification = self._verify(
            plan,
            evidence,
            weather,
            market,
            plan.intent,
            needs_weather=graph.needs_weather,
            needs_market=graph.needs_market,
        )
        agent_runs.append(
            verifier_timer.finish(
                summary="Applied non-LLM grounding, weather, eligibility, and dose gates.",
                input_sources=["agent_draft", "live_weather", "retrieved_evidence"],
                confidence=plan.confidence,
            )
        )
        verification_failed = any(check.status == "fail" for check in verification)
        needs_hitl = (
            verification_failed
            or plan.needs_human_review
            or plan.confidence < self.settings.hitl_confidence_threshold
        )
        trace = [
            TraceEvent(
                stage="consent_preflight",
                status="completed",
                detail=(
                    "Verified synthetic consent fixture before data access."
                    if self.synthetic_data_mode
                    else "Verified live AgriStack consent before data access."
                ),
            ),
            TraceEvent(
                stage="intent_router",
                status="completed",
                detail=graph.route_summary,
            ),
            TraceEvent(
                stage="live_tools",
                status="completed",
                detail=(
                    "Read labelled synthetic farmer, weather, and market context."
                    if self.synthetic_data_mode
                    else "Read live AgriStack, weather, and market context."
                ),
            ),
            TraceEvent(
                stage="image_processor",
                status="completed" if image_context else "skipped",
                detail=image_detail,
            ),
            TraceEvent(
                stage="memory_agent",
                status="completed",
                detail="Read the durable farmer twin and Qdrant evidence.",
            ),
            TraceEvent(
                stage=graph.specialist_agent,
                status="completed",
                detail="Gemini produced a specialist, schema-validated grounded draft.",
            ),
            TraceEvent(
                stage="reflection",
                status="completed",
                detail=(
                    "Applied one bounded revision."
                    if reflection.status == "revise"
                    else "Passed the bounded reflection contract."
                ),
            ),
            TraceEvent(
                stage="verifier",
                status="completed",
                detail="Applied deterministic grounding, weather, and dosage gates.",
            ),
        ]
        agent_runs.insert(
            0,
            root_timer.finish(
                summary=f"Completed the {graph.intent.value} agent graph.",
                input_sources=["live_consent", "farmer_request"],
                confidence=plan.confidence,
            ),
        )
        hitl_case_id = None
        if needs_hitl:
            hitl_case_id = str(uuid4())
            reason = (
                "Synthetic production data requires review before any delivery."
                if self.synthetic_data_mode
                else (
                    "A hard safety check failed."
                    if verification_failed
                    else "Human review required by confidence or plan policy."
                )
            )
            trace.append(TraceEvent(stage="human_in_the_loop", status="queued", detail=reason))
            self.memory.enqueue_hitl(
                self._hitl_case(
                    case_id=hitl_case_id,
                    request_id=request_id,
                    farmer_id=request.farmer_id,
                    plan=plan,
                    intent=plan.intent,
                    verification=verification,
                    evidence=evidence,
                    trace=trace,
                    agent_runs=agent_runs,
                    reason=reason,
                    safety_rule_set_version=self.settings.safety_rule_set_version,
                )
            )
        response = AdvisoryResponse(
            request_id=request_id,
            farmer_id=request.farmer_id,
            safety_rule_set_version=self.settings.safety_rule_set_version,
            intent=plan.intent,
            status="requires_human_review" if needs_hitl else "delivered",
            confidence=plan.confidence,
            recommendation=plan.recommendation,
            explanation=plan.explanation,
            evidence=evidence,
            reflection=ReflectionResult(status=reflection.status, notes=reflection.notes),
            verification=verification,
            trace=trace,
            agent_runs=agent_runs,
            hitl_case_id=hitl_case_id,
        )
        episode = {
            "request_id": request_id,
            "farmer_id": request.farmer_id,
            "intent": plan.intent.value,
            "query": request.query,
            "outcome": response.status,
            "recommendation": response.recommendation,
            "explanation": response.explanation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.memory.append_episode(episode)
        try:
            self.retrieval.append_episode(episode)
        except Exception:
            # PostgreSQL remains the system of record; indexing is retried by the worker.
            response.trace.append(
                TraceEvent(
                    stage="memory_index",
                    status="queued",
                    detail="Episode vector indexing will be retried.",
                )
            )
        return response

    def search_memory(self, request: MemorySearchRequest) -> list[dict[str, object]]:
        self._live_consent(
            request.farmer_id,
            frozenset({ConsentScope.ADVISORY, ConsentScope.ADVISORY_MEMORY}),
        )
        hits = self.retrieval.search("farmer_memory", request.query, filters={"farmer_id": request.farmer_id})
        return [hit.model_dump(mode="json") for hit in hits]

    def get_farmer(self, farmer_id: str) -> dict[str, object]:
        consent = self._live_consent(
            farmer_id, frozenset({ConsentScope.FARMER_PROFILE, ConsentScope.ADVISORY})
        )
        farmer, _ = self._refresh_farmer_context(farmer_id, consent)
        return farmer

    def sync_farmer(self, farmer_id: str) -> dict[str, object]:
        """Explicit service/admin sync used to validate onboarding source contracts."""

        consent = self._live_consent(
            farmer_id,
            frozenset({ConsentScope.FARMER_PROFILE, ConsentScope.ADVISORY}),
        )
        farmer, _ = self._refresh_farmer_context(farmer_id, consent)
        return farmer

    def ingest_knowledge(self, request: KnowledgeIngestRequest) -> str:
        """Write a source-reviewed document into the governed semantic store."""

        return self.retrieval.upsert_document(
            request.collection,
            document_id=request.document_id,
            title=request.title,
            content=request.content,
            metadata={
                "state": request.state,
                "source_name": request.source_name,
                "source_url": request.source_url,
                "source_updated_at": request.source_updated_at.isoformat(),
                "reviewed_by": request.reviewed_by,
                **request.metadata,
            },
        )

    def knowledge_stats(self) -> KnowledgeStats:
        return KnowledgeStats(runtime_mode="production", **self.retrieval.stats())

    def list_synthetic_farmers(self) -> list[DemoFarmerSummary]:
        """Return labelled fixture summaries only in explicit synthetic mode."""

        if self.seed_repository is None:
            return []
        summaries = [
            DemoFarmerSummary(**summary)
            for summary in self.seed_repository.list_farmer_summaries()
        ]
        if self.registered_farmers is not None:
            for farmer in self.registered_farmers.list():
                twin = farmer["digital_twin"]
                summaries.append(
                    DemoFarmerSummary(
                        farmer_id=str(farmer["farmer_id"]),
                        name=str(farmer["name"]),
                        state=str(farmer["state"]),
                        district=str(farmer["district"]),
                        preferred_language=str(farmer["preferred_language"]),
                        current_crop=str(twin["current_crop"]),
                        season=str(twin["season"]),
                        water_budget_mm=int(twin["water_budget_mm"]),
                        farm_size_hectares=float(twin["farm_size_hectares"]),
                    )
                )
        return sorted(summaries, key=lambda item: (item.state, item.district, item.farmer_id))

    def register_farmer(self, request: FarmerOnboardingRequest) -> dict[str, object]:
        if not self.synthetic_data_mode or self.registered_farmers is None:
            raise ToolDataUnavailableError(
                "Farmer onboarding registration is available only in synthetic production mode."
            )
        state_code = "".join(ch for ch in request.state.upper() if ch.isalpha())[:2] or "IN"
        sequence = 100000 + (len(self.registered_farmers.list()) % 900000)
        farmer_id = f"AGR_{state_code}_{sequence:06d}"
        while self.has_farmer(farmer_id):
            sequence += 1
            farmer_id = f"AGR_{state_code}_{sequence:06d}"
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        farmer = {
            "farmer_id": farmer_id,
            "name": request.name,
            "email": request.email.strip().lower(),
            "state": request.state,
            "district": request.district,
            "preferred_language": request.preferred_language,
            "synthetic_data": True,
            "consent": {
                "advisory": True,
                "consent_id": f"REG_CONSENT_{farmer_id}",
                "status": "granted",
                "purpose": "agricultural_advisory",
                "scopes": ["farmer_profile", "advisory", "advisory_memory"],
                "granted_at": now,
                "expires_at": "2030-12-31T23:59:59Z",
                "revoked_at": None,
            },
            "digital_twin": {
                "season": request.season,
                "current_crop": request.current_crop,
                "soil_fertility": request.soil_fertility,
                "water_budget_mm": request.water_budget_mm,
                "budget_inr": request.budget_inr,
                "eligible_schemes": ["PM-KISAN", "Soil Health Card"],
                "weather_alert": False,
                "farm_size_hectares": request.farm_size_hectares,
                "soil_type": request.soil_type,
                "irrigation_type": request.irrigation_type,
                "risk_flags": [],
            },
            "location": (
                {"latitude": request.latitude, "longitude": request.longitude}
                if request.latitude is not None and request.longitude is not None
                else None
            ),
            "assigned_officer_subjects": [],
        }
        return self.registered_farmers.upsert(farmer)

    def farmer_region(self, farmer_id: str) -> str | None:
        if self.registered_farmers is not None:
            registered = self.registered_farmers.get(farmer_id)
            if registered is not None:
                return str(registered.get("state")) or None
        if self.seed_repository is None:
            farmer = self.memory.get_farmer(farmer_id)
            return str(farmer["state"]) if farmer else None
        farmer = self.seed_repository.get_farmer(farmer_id)
        return str(farmer["state"]) if farmer else None

    def decide_hitl(self, case_id: str, request: HITLDecisionRequest) -> HITLCase | None:
        outcome = self.memory.decide_hitl(
            case_id,
            request.decision,
            request.reviewer_note,
            request.reviewer_name,
            request.edited_recommendation,
        )
        if outcome.state == "not_pending":
            raise HITLCaseNotPendingError(case_id)
        if outcome.state == "safety_blocked":
            raise HITLCaseSafetyBlockedError(case_id)
        return HITLCase(**outcome.case) if outcome.case else None

    def list_hitl_cases(self) -> list[HITLCase]:
        return [HITLCase(**case) for case in self.memory.list_hitl()]

    def get_hitl_case(self, case_id: str) -> HITLCase | None:
        case = self.memory.get_hitl(case_id)
        return HITLCase(**case) if case else None

    def has_farmer(self, farmer_id: str) -> bool:
        if self.registered_farmers is not None and self.registered_farmers.get(farmer_id) is not None:
            return True
        if self.seed_repository is not None and self.seed_repository.get_farmer(farmer_id) is not None:
            return True
        return self.memory.has_farmer(farmer_id)

    def upload_farmer_image(
        self,
        *,
        farmer_id: str,
        filename: str,
        content_type: str,
        payload: bytes,
    ) -> dict[str, object]:
        if self.farmer_images is None:
            raise ToolDataUnavailableError(
                "Image uploads are available only in synthetic production mode."
            )
        if not self.has_farmer(farmer_id):
            raise FarmerNotFoundError(farmer_id)
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Only JPEG, PNG, or WebP images are accepted.")
        if len(payload) > 5_000_000:
            raise ValueError("Image exceeds the 5 MB upload limit.")
        summary, suspected, confidence = AdvisoryService.analyse_crop_image(
            filename=filename, payload=payload
        )
        return self.farmer_images.save(
            image_id=str(uuid4()),
            farmer_id=farmer_id,
            filename=filename,
            content_type=content_type,
            payload=payload,
            analysis_summary=summary,
            suspected_issue=suspected,
            confidence=confidence,
        )

    def list_farmer_images(self, farmer_id: str) -> list[dict[str, object]]:
        if self.farmer_images is None:
            return []
        if not self.has_farmer(farmer_id):
            raise FarmerNotFoundError(farmer_id)
        return self.farmer_images.list_for_farmer(farmer_id)

    def purge_farmer_runtime_data(self, farmer_id: str) -> dict[str, int]:
        removed = self.memory.purge_farmer_runtime_data(farmer_id)
        self.retrieval.delete_farmer_episodes(farmer_id)
        return removed
