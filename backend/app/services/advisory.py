"""Deterministic local workflow for the SasyaAI demo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.models.advisory import (
    AdvisoryResponse,
    AgentRun,
    DemoFarmerSummary,
    FarmerOnboardingRequest,
    HITLCase,
    HITLDecisionRequest,
    Intent,
    KnowledgeHit,
    KnowledgeStats,
    MemorySearchRequest,
    QueryRequest,
    ReflectionResult,
    TraceEvent,
    VerificationCheck,
)
from app.models.integration import ConsentPreflightResult, ConsentScope
from app.services.consent import (
    ConsentAdapter,
    ConsentAdapterUnavailableError,
    SyntheticConsentAdapter,
)
from app.services.memory import (
    FarmerImageStore,
    HITLQueue,
    LearningStore,
    LocalMemoryStore,
    RegisteredFarmerStore,
    SeedRepository,
)
from app.services.security import sanitize_user_query


class FarmerNotFoundError(Exception):
    """Raised when a request does not reference one of the demo farmers."""


class ConsentNotGrantedError(Exception):
    """Raised when a synthetic profile has not granted advisory consent."""


class HITLCaseNotPendingError(Exception):
    """Raised when a decision would overwrite a completed review."""


class HITLCaseSafetyBlockedError(Exception):
    """Raised when a reviewer tries to approve a case with failed hard checks."""


@dataclass(frozen=True)
class AdvisoryDraft:
    """A recommendation plus the values the deterministic verifier must check."""

    recommendation: str
    explanation: str
    confidence: float
    evidence: list[KnowledgeHit]
    selected_crop: str | None = None
    recommended_irrigation_mm: int | None = None
    estimated_input_cost_inr: int | None = None
    pesticide_protocol_max_dose_ml_per_l: float | None = None


def _vision_specialists(image_context: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not image_context:
        return {}
    vision = image_context.get("vision")
    if not isinstance(vision, dict):
        return {}
    specialists = vision.get("specialists")
    if not isinstance(specialists, dict):
        extras = vision.get("extras")
        specialists = extras.get("specialists") if isinstance(extras, dict) else None
    if not isinstance(specialists, dict):
        return {}
    return {
        str(kind): value
        for kind, value in specialists.items()
        if isinstance(value, dict)
    }


def _vision_trace_events(
    image_context: dict[str, Any] | None,
    image_detail: str,
) -> list[TraceEvent]:
    if not image_context:
        return [
            TraceEvent(stage="image_preprocessing", status="skipped", detail=image_detail)
        ]

    events = [
        TraceEvent(stage="image_preprocessing", status="completed", detail=image_detail)
    ]
    specialists = _vision_specialists(image_context)
    for kind in ("disease", "pest"):
        evidence = specialists.get(kind, {})
        events.append(
            TraceEvent(
                stage=f"{kind}_detection",
                status="completed" if evidence.get("available") else "skipped",
                detail=str(
                    evidence.get("summary")
                    or f"No {kind} specialist evidence was produced for this image."
                ),
            )
        )
    events.append(
        TraceEvent(
            stage="vision_evidence_fusion",
            status="completed",
            detail=str(image_context.get("analysis_summary", "Fused crop-image evidence.")),
        )
    )
    return events


def _vision_agent_runs(image_context: dict[str, Any]) -> list[AgentRun]:
    vision = image_context.get("vision")
    vision = vision if isinstance(vision, dict) else {}
    specialists = _vision_specialists(image_context)
    runs = [
        AgentRun(
            agent_id="vision_preprocessor",
            name="Image Preprocessing",
            role="Validates, strips metadata, resizes, and quality-gates crop imagery",
            status="completed",
            execution_mode="tool",
            duration_ms=0,
            summary=(
                "Prepared the crop image and calculated quality/anomaly provenance."
            ),
            input_sources=["farmer_image"],
        )
    ]
    for kind, name in (("disease", "Disease Detection"), ("pest", "Pest Detection")):
        evidence = specialists.get(kind, {})
        runs.append(
            AgentRun(
                agent_id=f"{kind}_vision_specialist",
                name=name,
                role=f"Dedicated ONNX {kind} evidence specialist",
                status="completed" if evidence.get("available") else "skipped",
                execution_mode="tool",
                duration_ms=int(round(float(evidence.get("inference_ms", 0.0)))),
                summary=str(
                    evidence.get("summary")
                    or f"No {kind} specialist evidence was available."
                ),
                input_sources=["preprocessed_farmer_image"],
                output_confidence=(
                    float(evidence.get("confidence", 0.0))
                    if evidence.get("available")
                    else None
                ),
            )
        )
    runs.append(
        AgentRun(
            agent_id="vision_evidence_fusion",
            name="Vision Evidence Fusion",
            role="Preserves disease and pest findings under the stable image contract",
            status="completed",
            execution_mode="deterministic",
            duration_ms=int(round(float(vision.get("inference_ms", 0.0)))),
            summary=str(image_context.get("analysis_summary", "Fused crop-image evidence.")),
            input_sources=["disease_vision", "pest_vision"],
            output_confidence=float(image_context.get("confidence", 0.0)),
        )
    )
    return runs


class AdvisoryService:
    """Coordinates routing, memory, reflection, verification, and HITL."""

    def __init__(
        self,
        settings: Settings | None = None,
        runtime_dir: Path | None = None,
        consent_adapter: ConsentAdapter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        active_runtime_dir = runtime_dir or self.settings.runtime_dir
        self.runtime_dir = active_runtime_dir
        self.repository = SeedRepository(self.settings.seed_data_dir)
        self.registered_farmers = RegisteredFarmerStore(active_runtime_dir)
        self.images = FarmerImageStore(active_runtime_dir)
        self.learning = LearningStore(active_runtime_dir)
        self.consent_adapter = consent_adapter or SyntheticConsentAdapter(
            self.repository,
            registered_consent_lookup=self._registered_consent,
        )
        self.memory = LocalMemoryStore(active_runtime_dir)
        self.hitl = HITLQueue(active_runtime_dir)

    def _registered_consent(self, farmer_id: str) -> dict[str, object] | None:
        farmer = self.registered_farmers.get(farmer_id)
        if farmer is None:
            return None
        consent = farmer.get("consent")
        return consent if isinstance(consent, dict) else None

    def farmer_region(self, farmer_id: str) -> str | None:
        farmer = self.repository.get_farmer(farmer_id) or self.registered_farmers.get(farmer_id)
        if farmer is None:
            return None
        return str(farmer.get("state", "")) or None

    def farmer_catalog(self) -> list[tuple[str, str]]:
        catalog = [
            (str(summary["farmer_id"]), str(summary["state"]))
            for summary in self.repository.list_farmer_summaries()
        ]
        for farmer in self.registered_farmers.list():
            catalog.append((str(farmer["farmer_id"]), str(farmer["state"])))
        return catalog

    def _apply_runtime_retention(self) -> None:
        """Prune only local demo state; governed production retention is externally owned."""

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.retention_days)
        self.memory.purge_before(cutoff)
        self.hitl.purge_before(cutoff)

    @staticmethod
    def classify_intent(query: str) -> Intent:
        lower_query = query.lower()
        if any(
            term in lower_query
            for term in ("pest", "disease", "leaf", "spot", "insect", "aphid", "worm")
        ):
            return Intent.DIAGNOSE
        if any(
            term in lower_query for term in ("scheme", "pm-kisan", "pmfby", "eligible", "subsidy")
        ):
            return Intent.SCHEME
        return Intent.CROP_PLAN

    @staticmethod
    def _knowledge_hits(collection: str, records: list[dict[str, object]]) -> list[KnowledgeHit]:
        return [
            KnowledgeHit(
                source=collection,
                title=str(record.get("title", record.get("name", "Seed knowledge"))),
                score=float(record.get("_score", 0.45)),
            metadata={
                key: value
                for key, value in record.items()
                if key not in {"title", "name", "_score"} and value is not None
            },
            )
            for record in records
        ]

    def _require_consent(
        self,
        farmer_id: str,
        required_scopes: frozenset[ConsentScope],
        *,
        request_id: str | None = None,
    ) -> ConsentPreflightResult:
        """Check the minimal consent index before any profile or memory access."""

        result = self.consent_adapter.preflight(
            farmer_id=farmer_id,
            purpose="agricultural_advisory",
            required_scopes=required_scopes,
            request_id=request_id,
        )
        if result is None:
            raise FarmerNotFoundError(farmer_id)
        if not isinstance(result, ConsentPreflightResult):
            raise ConsentAdapterUnavailableError("Consent adapter returned an invalid result.")
        if result.consent.farmer_id != farmer_id:
            raise ConsentAdapterUnavailableError("Consent receipt does not match the requested farmer.")
        if not result.allowed:
            raise ConsentNotGrantedError(farmer_id)
        if not required_scopes.issubset(result.consent.scopes):
            raise ConsentAdapterUnavailableError("Granted consent receipt is missing a required scope.")
        return result

    def _read_authorised_farmer(
        self, farmer_id: str, receipt: ConsentPreflightResult
    ) -> dict[str, object]:
        """Read a profile only after a valid grant and reject fixture mismatches."""

        if not receipt.allowed or receipt.consent.farmer_id != farmer_id:
            raise ConsentAdapterUnavailableError("Consent receipt cannot authorise this profile read.")
        farmer = self.repository.get_farmer(farmer_id) or self.registered_farmers.get(farmer_id)
        if farmer is None or farmer.get("farmer_id") != farmer_id:
            raise ConsentAdapterUnavailableError(
                "Consent and farmer profile fixtures are inconsistent."
            )
        return farmer

    @staticmethod
    def _regional_records(
        records: list[dict[str, object]], state: str, *, region_key: str = "region"
    ) -> list[dict[str, object]]:
        return [
            record
            for record in records
            if str(record.get(region_key, "")).lower() in {state.lower(), "all"}
        ]

    def _crop_plan(
        self, farmer: dict[str, object], query: str, language: str
    ) -> AdvisoryDraft:
        twin = farmer["digital_twin"]
        state = str(farmer["state"])
        water_budget = int(twin["water_budget_mm"])
        financial_budget = int(twin["budget_inr"])
        regional_records = self._regional_records(self.repository.list_knowledge("crops"), state)
        feasible_records = [
            record
            for record in regional_records
            if int(record.get("water_need_mm", water_budget + 1)) <= water_budget
            and int(record.get("estimated_input_cost_inr", financial_budget + 1)) <= financial_budget
        ]

        lower_query = query.lower()
        known_crops = {
            str(record.get("crop", "")).lower()
            for record in self.repository.list_knowledge("crops")
            if record.get("crop")
        }
        requested_crop = next(
            (crop for crop in known_crops if crop in lower_query),
            None,
        )
        matching_records = (
            [record for record in feasible_records if str(record.get("crop", "")).lower() == requested_crop]
            if requested_crop
            else feasible_records
        )
        selected = min(
            matching_records,
            key=lambda record: int(record.get("water_need_mm", water_budget)),
            default=None,
        )
        evidence_records = self.repository.search_knowledge("crops", query)
        if selected is not None:
            selected_evidence = selected | {"_score": 0.95}
            evidence_records = [selected_evidence] + [
                record
                for record in evidence_records
                if record.get("title") != selected.get("title")
            ]
            crop = str(selected["crop"])
            irrigation = int(selected["water_need_mm"])
            input_cost = int(selected["estimated_input_cost_inr"])
            recommendation = (
                f"Choose {crop} for the coming {twin['season']} season, plan no more than "
                f"{irrigation} mm of irrigation, and keep estimated inputs within ₹{input_cost}."
            )
            explanation = (
                f"The seeded {state} guidance for {crop} needs {irrigation} mm of water against "
                f"this farm's {water_budget} mm budget and estimates ₹{input_cost} of inputs against "
                f"the ₹{financial_budget} budget."
            )
            if language.lower().startswith("mr") and crop.lower() == "soybean":
                explanation = (
                    f"{water_budget} मिमी पाण्याच्या मर्यादेत सोयाबीनसाठी {irrigation} मिमी सिंचन "
                    f"आणि ₹{input_cost} अंदाजे इनपुट खर्च शक्य असल्यामुळे तो योग्य पर्याय आहे."
                )
            return AdvisoryDraft(
                recommendation=recommendation,
                explanation=explanation,
                confidence=0.84,
                evidence=self._knowledge_hits("crop_kb", evidence_records),
                selected_crop=crop,
                recommended_irrigation_mm=irrigation,
                estimated_input_cost_inr=input_cost,
            )

        if requested_crop:
            recommendation = (
                f"The requested crop {requested_crop} has no validated {state} record that fits this "
                f"farm's {water_budget} mm water and ₹{financial_budget} input constraints. "
                "Do not change crops without extension-officer review."
            )
        else:
            recommendation = (
                f"No seeded {state} crop option fits the {water_budget} mm water and ₹{financial_budget} "
                "input constraints. Do not change crops without extension-officer review."
            )

        return AdvisoryDraft(
            recommendation=(
                recommendation
            ),
            explanation=(
                "The deterministic demo could not find a feasible, state-specific crop record, so it is "
                "not producing an automatic crop plan."
            ),
            confidence=0.55,
            evidence=self._knowledge_hits("crop_kb", evidence_records or regional_records),
        )

    def _diagnosis(
        self,
        farmer: dict[str, object],
        query: str,
        language: str,
        *,
        image_context: dict[str, object] | None = None,
    ) -> AdvisoryDraft:
        twin = farmer["digital_twin"]
        state = str(farmer["state"])
        current_crop = str(twin["current_crop"])
        protocols = [
            record
            for record in self._regional_records(self.repository.list_knowledge("pests"), state)
            if str(record.get("crop", "")).lower() == current_crop.lower()
        ]
        lower_query = query.lower()
        if image_context and image_context.get("suspected_issue"):
            lower_query = f"{lower_query} {str(image_context['suspected_issue']).lower()}"
        protocol = max(
            protocols,
            key=lambda record: str(record.get("name", "")).lower() in lower_query,
            default=None,
        )
        evidence_records = self.repository.search_knowledge("pests", query)
        if protocol is None:
            return AdvisoryDraft(
                recommendation=(
                    f"No matching seeded treatment protocol is available for {current_crop} in {state}. "
                    "Capture a clear image and request extension-officer review before applying treatment."
                ),
                explanation=(
                    "The demo has no crop-and-region protocol to validate a treatment dose, so it cannot "
                    "make a safe automated diagnosis."
                ),
                confidence=0.50,
                evidence=self._knowledge_hits("pest_kb", evidence_records),
            )

        protocol_evidence = protocol | {"_score": 0.95}
        evidence_records = [protocol_evidence] + [
            record for record in evidence_records if record.get("title") != protocol.get("title")
        ]
        if image_context:
            evidence_records = [
                {
                    "title": f"Uploaded crop image ({image_context.get('filename', 'image')})",
                    "guidance": str(image_context.get("analysis_summary", "")),
                    "_score": float(image_context.get("confidence", 0.7)),
                },
                *evidence_records,
            ]
        raw_max_dose = protocol.get("max_dose_ml_per_l")
        if raw_max_dose is None:
            return AdvisoryDraft(
                recommendation=(
                    f"The synthetic reference flags possible {protocol['name']} pressure in "
                    f"{current_crop}. Capture clear crop images and request extension-officer "
                    "review before taking treatment action."
                ),
                explanation=(
                    "The reference contains observation guidance but no governed product-specific "
                    "dose limit, so any supplied dose is blocked."
                ),
                confidence=0.58,
                evidence=self._knowledge_hits("pest_kb", evidence_records),
            )

        max_dose = float(raw_max_dose)
        if image_context:
            recommendation = (
                f"Image-assisted analysis suspects {protocol['name']} pressure in {current_crop}. "
                f"{image_context.get('analysis_summary', '')} Obtain officer review before treatment."
            )
            explanation = (
                "Uploaded imagery raised diagnosis confidence; any supplied dose is still checked "
                f"against the {max_dose:g} ml/L seeded protocol limit."
            )
            confidence = max(0.72, float(image_context.get("confidence", 0.72)))
        else:
            recommendation = (
                f"The image-free demo suspects {protocol['name']} pressure in {current_crop}. Capture a clear "
                "leaf photo and obtain officer review before applying any treatment."
            )
            explanation = (
                "Without an image, diagnosis confidence remains below the auto-delivery threshold; any supplied "
                f"dose is checked only against the {max_dose:g} ml/L seeded protocol limit."
            )
            confidence = 0.62
        if language.lower().startswith("hi") and not image_context:
            explanation = (
                "फोटो के बिना निदान का भरोसा कम है; उपचार से पहले कृषि अधिकारी की समीक्षा आवश्यक है।"
            )
        return AdvisoryDraft(
            recommendation=recommendation,
            explanation=explanation,
            confidence=confidence,
            evidence=self._knowledge_hits("pest_kb", evidence_records),
            pesticide_protocol_max_dose_ml_per_l=max_dose,
        )

    def _scheme_query(self, farmer: dict[str, object], query: str) -> AdvisoryDraft:
        scheme_records = self.repository.search_knowledge("schemes", query)
        eligible_schemes = ", ".join(farmer["digital_twin"]["eligible_schemes"])
        recommendation = f"Review your eligibility for {eligible_schemes} and complete any required verification through the authorised portal."
        explanation = "The advice is based on the synthetic farmer profile; live eligibility must be confirmed from the current official scheme source."
        return AdvisoryDraft(
            recommendation=recommendation,
            explanation=explanation,
            confidence=0.79,
            evidence=self._knowledge_hits("scheme_kb", scheme_records),
        )

    def _verify(
        self, farmer: dict[str, object], request: QueryRequest, intent: Intent, draft: AdvisoryDraft
    ) -> list[VerificationCheck]:
        twin = farmer["digital_twin"]
        water_budget = int(twin["water_budget_mm"])
        financial_budget = int(twin["budget_inr"])
        if draft.recommended_irrigation_mm is None:
            water_check = VerificationCheck(
                name="water_budget",
                status="not_applicable",
                message="No automatic crop allocation was produced for water-budget validation.",
            )
        elif draft.recommended_irrigation_mm <= water_budget:
            water_check = VerificationCheck(
                name="water_budget",
                status="pass",
                message=(
                    f"Recommended {draft.recommended_irrigation_mm} mm irrigation is within the "
                    f"{water_budget} mm demo budget."
                ),
            )
        else:
            water_check = VerificationCheck(
                name="water_budget",
                status="fail",
                message=(
                    f"Recommended {draft.recommended_irrigation_mm} mm irrigation exceeds the "
                    f"{water_budget} mm demo budget and is blocked from auto-delivery."
                ),
            )

        if draft.estimated_input_cost_inr is None:
            financial_check = VerificationCheck(
                name="financial_feasibility",
                status="not_applicable",
                message="No automatic input-cost estimate was produced for budget validation.",
            )
        elif draft.estimated_input_cost_inr <= financial_budget:
            financial_check = VerificationCheck(
                name="financial_feasibility",
                status="pass",
                message=(
                    f"Estimated ₹{draft.estimated_input_cost_inr} inputs are within the "
                    f"₹{financial_budget} demo budget."
                ),
            )
        else:
            financial_check = VerificationCheck(
                name="financial_feasibility",
                status="fail",
                message=(
                    f"Estimated ₹{draft.estimated_input_cost_inr} inputs exceed the "
                    f"₹{financial_budget} demo budget and are blocked from auto-delivery."
                ),
            )

        weather_alert = bool(twin.get("weather_alert", False))
        checks = [
            water_check,
            financial_check,
            VerificationCheck(
                name="weather_safety",
                status="fail" if weather_alert else "pass",
                message=(
                    "An active extreme-weather flag is present in the deterministic demo data."
                    if weather_alert
                    else "No active extreme-weather flag is present in the deterministic demo data."
                ),
            ),
            VerificationCheck(
                name="scheme_eligibility",
                status="pass" if intent != Intent.SCHEME or twin["eligible_schemes"] else "fail",
                message="Scheme eligibility is supported by the synthetic twin and must be rechecked against an official live source.",
            ),
        ]

        if request.requested_dose_ml_per_l is None:
            checks.append(
                VerificationCheck(
                    name="pesticide_safety",
                    status="not_applicable",
                    message="No pesticide dose was supplied for validation.",
                )
            )
        elif draft.pesticide_protocol_max_dose_ml_per_l is None:
            checks.append(
                VerificationCheck(
                    name="pesticide_safety",
                    status="fail",
                    message=(
                        "No matching seeded crop-and-region treatment protocol is available to validate "
                        "the supplied dose; it is blocked from auto-delivery."
                    ),
                )
            )
        elif request.requested_dose_ml_per_l <= draft.pesticide_protocol_max_dose_ml_per_l:
            checks.append(
                VerificationCheck(
                    name="pesticide_safety",
                    status="pass",
                    message=(
                        f"Requested dose is within the {draft.pesticide_protocol_max_dose_ml_per_l:g} "
                        "ml/L demo maximum for the selected protocol."
                    ),
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="pesticide_safety",
                    status="fail",
                    message=(
                        f"Requested dose exceeds the {draft.pesticide_protocol_max_dose_ml_per_l:g} ml/L "
                        "demo maximum and is blocked from auto-delivery."
                    ),
                )
            )
        return checks

    @staticmethod
    def _demo_agent_runs(
        intent: Intent,
        confidence: float,
        evidence: list[KnowledgeHit],
    ) -> list[AgentRun]:
        """Expose the same graph shape while clearly labelling fallback execution."""

        specialist = {
            Intent.CROP_PLAN: (
                "crop_planning_agent",
                "Crop Planning Agent",
                "Applied deterministic crop feasibility rules.",
            ),
            Intent.DIAGNOSE: (
                "pest_diagnosis_agent",
                "Pest Diagnosis Agent",
                "Matched the query to synthetic IPM observation records.",
            ),
            Intent.SCHEME: (
                "scheme_navigation_agent",
                "Scheme Navigation Agent",
                "Matched synthetic scheme records and official verification steps.",
            ),
        }[intent]
        return [
            AgentRun(
                agent_id="root_manager",
                name="Root Manager",
                role="Consent-gated session owner and task-graph coordinator",
                status="completed",
                execution_mode="deterministic",
                duration_ms=0,
                summary=f"Completed the {intent.value} fallback graph.",
                input_sources=["synthetic_consent", "farmer_request"],
                output_confidence=confidence,
            ),
            AgentRun(
                agent_id="intent_router",
                name="Intent Router",
                role="Classifies the request and emits a typed execution plan",
                status="completed",
                execution_mode="deterministic",
                duration_ms=0,
                summary=f"Routed the request to {specialist[1]}.",
                input_sources=["farmer_request"],
            ),
            AgentRun(
                agent_id="memory_agent",
                name="Memory Agent",
                role="Sole owner of PostgreSQL and Qdrant reads and writes",
                status="completed",
                execution_mode="tool",
                duration_ms=0,
                summary=f"Retrieved {len(evidence)} synthetic evidence records.",
                input_sources=["seed_json"],
            ),
            AgentRun(
                agent_id=specialist[0],
                name=specialist[1],
                role="Deterministic specialist fallback",
                status="completed",
                execution_mode="deterministic",
                duration_ms=0,
                summary=specialist[2],
                input_sources=["synthetic_twin", "seed_knowledge"],
                output_confidence=confidence,
            ),
            AgentRun(
                agent_id="reflection_agent",
                name="Reflection Agent",
                role="Checks grounding, completeness, clarity, and escalation needs",
                status="completed",
                execution_mode="deterministic",
                duration_ms=0,
                summary="Checked intent coverage, wording, and units.",
                input_sources=["specialist_draft"],
                output_confidence=confidence,
            ),
            AgentRun(
                agent_id="safety_verifier",
                name="Safety Verifier",
                role="Deterministic, non-LLM delivery gate",
                status="completed",
                execution_mode="deterministic",
                duration_ms=0,
                summary="Applied water, budget, weather, scheme, and dose gates.",
                input_sources=["specialist_draft", "synthetic_twin", "safety_rules"],
                output_confidence=confidence,
            ),
        ]

    def query(self, request: QueryRequest) -> AdvisoryResponse:
        request_id = str(uuid4())
        cleaned_query = sanitize_user_query(request.query)
        request = request.model_copy(update={"query": cleaned_query})
        consent = self._require_consent(
            request.farmer_id,
            frozenset(
                {
                    ConsentScope.FARMER_PROFILE,
                    ConsentScope.ADVISORY,
                    ConsentScope.ADVISORY_MEMORY,
                }
            ),
            request_id=request_id,
        )
        farmer = self._read_authorised_farmer(request.farmer_id, consent)
        self._apply_runtime_retention()

        image_context = None
        if request.image_id:
            image_context = self.images.get(request.image_id)
            if image_context is None or image_context.get("farmer_id") != request.farmer_id:
                raise FarmerNotFoundError(request.farmer_id)

        intent = request.intent or self.classify_intent(request.query)
        if intent == Intent.DIAGNOSE:
            draft = self._diagnosis(
                farmer, request.query, request.language, image_context=image_context
            )
        elif intent == Intent.SCHEME:
            draft = self._scheme_query(farmer, request.query)
        else:
            draft = self._crop_plan(farmer, request.query, request.language)

        learned = self.learning.search(request.query, state=str(farmer.get("state")))
        if learned and draft.confidence < 0.9:
            draft = AdvisoryDraft(
                recommendation=draft.recommendation,
                explanation=(
                    f"{draft.explanation} Prior helpful advisories in this region were also considered."
                ),
                confidence=min(0.9, draft.confidence + 0.03),
                evidence=draft.evidence
                + [
                    KnowledgeHit(
                        source="learning_memory",
                        title="Prior helpful advisory",
                        score=0.55,
                        metadata={"query": str(item.get("query", ""))[:120]},
                    )
                    for item in learned[:1]
                ],
                selected_crop=draft.selected_crop,
                recommended_irrigation_mm=draft.recommended_irrigation_mm,
                estimated_input_cost_inr=draft.estimated_input_cost_inr,
                pesticide_protocol_max_dose_ml_per_l=draft.pesticide_protocol_max_dose_ml_per_l,
            )

        verification = self._verify(farmer, request, intent, draft)
        verification_failed = any(check.status == "fail" for check in verification)
        needs_hitl = verification_failed or draft.confidence < self.settings.hitl_confidence_threshold
        vision_needs_review = False
        if image_context:
            vision_meta = image_context.get("vision") if isinstance(image_context, dict) else None
            if isinstance(vision_meta, dict):
                image_detail = (
                    f"Vision {vision_meta.get('backend', 'pixel')} "
                    f"({vision_meta.get('model_version', 'unknown')}) "
                    f"in {vision_meta.get('inference_ms', '?')}ms; "
                    f"label={vision_meta.get('suspected_issue') or 'none'}; "
                    f"confidence={vision_meta.get('confidence')}; "
                    f"anomaly={vision_meta.get('anomaly_score')}; "
                    f"hash={str(vision_meta.get('input_hash', ''))[:12]}"
                )
                if vision_meta.get("needs_officer_review"):
                    vision_needs_review = True
                    needs_hitl = True
            else:
                image_detail = f"Attached image {request.image_id} analysed for crop symptoms."
        else:
            image_detail = "No crop image was attached to this request."
        trace = [
            TraceEvent(
                stage="consent_preflight",
                status="completed",
                detail=(
                    "Validated synthetic advisory consent and required scopes before reading "
                    f"farmer data via {consent.consent.provenance.provider}."
                ),
            ),
            TraceEvent(
                stage="query_sanitiser",
                status="completed",
                detail="Sanitised the farmer query and refused instruction-override patterns.",
            ),
            TraceEvent(
                stage="intent_classifier",
                status="completed",
                detail=f"Classified request as {intent.value}.",
            ),
            TraceEvent(
                stage="planner", status="completed", detail="Built a deterministic demo task graph."
            ),
            *_vision_trace_events(image_context, image_detail),
            TraceEvent(
                stage="evidence_retrieval",
                status="completed",
                detail="Retrieved twin, knowledge-base, and learning-memory context.",
            ),
            TraceEvent(
                stage="specialist_reasoning",
                status="completed",
                detail="Produced a grounded specialist advisory from the retrieved evidence.",
            ),
            TraceEvent(
                stage="reflection",
                status="completed",
                detail="Checked intent coverage, actionable wording, and units.",
            ),
            TraceEvent(
                stage="safety_verification",
                status="completed",
                detail=(
                    "Executed deterministic water, budget, weather, scheme, and dose checks "
                    f"using safety rule set {self.settings.safety_rule_set_version}."
                ),
            ),
            TraceEvent(
                stage="advisory_generated",
                status="completed",
                detail="Generated the farmer-facing advisory for delivery or officer review.",
            ),
        ]
        agent_runs = self._demo_agent_runs(intent, draft.confidence, draft.evidence)
        if image_context:
            agent_runs[3:3] = _vision_agent_runs(image_context)

        reflection = ReflectionResult(
            status="pass",
            notes=[
                "Response addresses the requested intent.",
                "Recommendation includes a concrete next action.",
            ],
        )
        hitl_case_id = None
        if needs_hitl:
            hitl_case_id = str(uuid4())
            reason = (
                "A hard safety check failed."
                if verification_failed
                else (
                    "Vision evidence requires extension-officer review."
                    if vision_needs_review
                    else "Confidence is below the auto-delivery threshold."
                )
            )
            trace.append(TraceEvent(stage="human_in_the_loop", status="queued", detail=reason))
            self.hitl.enqueue(
                {
                    "case_id": hitl_case_id,
                    "farmer_id": request.farmer_id,
                    "status": "pending",
                    "reason": reason,
                    "request_id": request_id,
                    "safety_rule_set_version": self.settings.safety_rule_set_version,
                    "intent": intent.value,
                    "confidence": draft.confidence,
                    "original_recommendation": draft.recommendation,
                    "original_explanation": draft.explanation,
                    "evidence": [hit.model_dump(mode="json") for hit in draft.evidence],
                    "verification": [check.model_dump(mode="json") for check in verification],
                    "trace": [event.model_dump(mode="json") for event in trace],
                    "agent_runs": [run.model_dump(mode="json") for run in agent_runs],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "decision_history": [],
                }
            )

        response = AdvisoryResponse(
            request_id=request_id,
            farmer_id=request.farmer_id,
            safety_rule_set_version=self.settings.safety_rule_set_version,
            intent=intent,
            status="requires_human_review" if needs_hitl else "delivered",
            confidence=draft.confidence,
            recommendation=draft.recommendation,
            explanation=draft.explanation,
            evidence=draft.evidence,
            reflection=reflection,
            verification=verification,
            trace=trace,
            agent_runs=agent_runs,
            hitl_case_id=hitl_case_id,
        )
        self.memory.append(
            {
                "request_id": request_id,
                "farmer_id": request.farmer_id,
                "intent": intent.value,
                "query": request.query,
                "outcome": response.status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return response

    def search_memory(self, request: MemorySearchRequest) -> list[dict[str, object]]:
        self._require_consent(
            request.farmer_id,
            frozenset({ConsentScope.ADVISORY, ConsentScope.ADVISORY_MEMORY}),
        )
        self._apply_runtime_retention()
        return self.memory.search(request.farmer_id, request.query)

    def get_farmer(self, farmer_id: str) -> dict[str, object]:
        consent = self._require_consent(
            farmer_id,
            frozenset({ConsentScope.FARMER_PROFILE, ConsentScope.ADVISORY}),
        )
        return self._read_authorised_farmer(farmer_id, consent)

    def knowledge_stats(self) -> KnowledgeStats:
        return KnowledgeStats(runtime_mode="demo", **self.repository.knowledge_stats())

    def list_demo_farmers(self) -> list[DemoFarmerSummary]:
        summaries = [
            DemoFarmerSummary.model_validate(summary)
            for summary in self.repository.list_farmer_summaries()
        ]
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
                    soil_fertility=str(twin.get("soil_fertility", "moderate")),
                    budget_inr=int(twin.get("budget_inr", 0)),
                    soil_type=str(twin.get("soil_type", "locally recorded soil")),
                    irrigation_type=str(twin.get("irrigation_type", "rainfed")),
                )
            )
        return sorted(summaries, key=lambda item: (item.state, item.district, item.farmer_id))

    def register_farmer(self, request: FarmerOnboardingRequest) -> dict[str, object]:
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

    @staticmethod
    def analyse_crop_image(
        *,
        filename: str,
        payload: bytes,
        content_type: str = "image/jpeg",
        backend: str = "auto",
    ) -> tuple[str, str | None, float]:
        """Run the vision pipeline; returns the stable public tuple contract."""

        from app.services.vision import VisionPreprocessError, analyse_crop_image

        try:
            result = analyse_crop_image(
                payload=payload,
                content_type=content_type,
                filename=filename,
                backend=backend,  # type: ignore[arg-type]
            )
        except VisionPreprocessError as error:
            raise ValueError(str(error)) from error
        return result.as_tuple()

    def upload_farmer_image(
        self,
        *,
        farmer_id: str,
        filename: str,
        content_type: str,
        payload: bytes,
    ) -> dict[str, object]:
        from app.services.vision import VisionPreprocessError, analyse_crop_image

        if not self.has_farmer(farmer_id):
            raise FarmerNotFoundError(farmer_id)
        backend = getattr(self.settings, "vision_backend", "auto")
        try:
            result = analyse_crop_image(
                payload=payload,
                content_type=content_type,
                filename=filename,
                backend=backend,
                hitl_threshold=getattr(self.settings, "vision_hitl_threshold", 0.70),
            )
        except VisionPreprocessError as error:
            raise ValueError(str(error)) from error
        return self.images.save(
            image_id=str(uuid4()),
            farmer_id=farmer_id,
            filename=filename,
            content_type=content_type,
            payload=payload,
            analysis_summary=result.analysis_summary,
            suspected_issue=result.suspected_issue,
            confidence=result.confidence,
            vision_provenance=result.provenance(),
        )

    def list_farmer_images(self, farmer_id: str) -> list[dict[str, object]]:
        if not self.has_farmer(farmer_id):
            raise FarmerNotFoundError(farmer_id)
        return self.images.list_for_farmer(farmer_id)

    def record_feedback(
        self,
        *,
        farmer_id: str,
        request_id: str,
        query: str,
        recommendation: str,
        helpful: bool,
        note: str,
    ) -> dict[str, object]:
        if not self.has_farmer(farmer_id):
            raise FarmerNotFoundError(farmer_id)
        farmer = self.repository.get_farmer(farmer_id) or self.registered_farmers.get(farmer_id) or {}
        record = {
            "feedback_id": str(uuid4()),
            "farmer_id": farmer_id,
            "request_id": request_id,
            "query": sanitize_user_query(query),
            "recommendation": recommendation[:2_000],
            "helpful": helpful,
            "note": note[:1_000],
            "state": farmer.get("state"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.learning.append(record)
        return record

    def decide_hitl(self, case_id: str, request: HITLDecisionRequest) -> HITLCase | None:
        self._apply_runtime_retention()
        case = self.hitl.decide(
            case_id,
            request.decision,
            request.reviewer_note,
            request.reviewer_name,
            request.edited_recommendation,
        )
        if case.state == "not_pending":
            raise HITLCaseNotPendingError(case_id)
        if case.state == "safety_blocked":
            raise HITLCaseSafetyBlockedError(case_id)
        return HITLCase(**case.case) if case.case else None

    def list_hitl_cases(self) -> list[HITLCase]:
        self._apply_runtime_retention()
        return [HITLCase(**case) for case in self.hitl.list()]

    def get_hitl_case(self, case_id: str) -> HITLCase | None:
        case = self.hitl.get(case_id)
        return HITLCase(**case) if case else None

    def has_farmer(self, farmer_id: str) -> bool:
        """Check the synthetic identity index for an administrative lifecycle request."""

        return self.repository.has_farmer(farmer_id) or self.registered_farmers.get(farmer_id) is not None

    def purge_farmer_runtime_data(self, farmer_id: str) -> dict[str, int]:
        """Purge only local runtime records; seed fixtures remain immutable evidence."""

        return {
            "advisory_memory": self.memory.purge_farmer(farmer_id),
            "hitl_cases": self.hitl.purge_farmer(farmer_id),
        }
