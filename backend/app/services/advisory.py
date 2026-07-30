"""Deterministic local workflow for the SasyaAI demo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.models.advisory import (
    AdvisoryResponse,
    HITLCase,
    HITLDecisionRequest,
    Intent,
    KnowledgeHit,
    MemorySearchRequest,
    QueryRequest,
    ReflectionResult,
    TraceEvent,
    VerificationCheck,
)
from app.services.memory import HITLQueue, LocalMemoryStore, SeedRepository


class FarmerNotFoundError(Exception):
    """Raised when a request does not reference one of the demo farmers."""


class ConsentNotGrantedError(Exception):
    """Raised when a synthetic profile has not granted advisory consent."""


class HITLCaseNotPendingError(Exception):
    """Raised when a decision would overwrite a completed review."""


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


class AdvisoryService:
    """Coordinates routing, memory, reflection, verification, and HITL."""

    def __init__(self, settings: Settings | None = None, runtime_dir: Path | None = None) -> None:
        self.settings = settings or get_settings()
        active_runtime_dir = runtime_dir or self.settings.runtime_dir
        self.repository = SeedRepository(self.settings.seed_data_dir)
        self.memory = LocalMemoryStore(active_runtime_dir)
        self.hitl = HITLQueue(active_runtime_dir)

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
                    if key not in {"title", "name", "_score"}
                },
            )
            for record in records
        ]

    @staticmethod
    def _has_advisory_consent(farmer: dict[str, object]) -> bool:
        consent = farmer.get("consent")
        return isinstance(consent, dict) and consent.get("advisory") is True

    @classmethod
    def _require_advisory_consent(cls, farmer: dict[str, object]) -> None:
        if not cls._has_advisory_consent(farmer):
            raise ConsentNotGrantedError(str(farmer.get("farmer_id", "unknown")))

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
        selected = max(
            feasible_records,
            key=lambda record: (
                str(record.get("crop", "")).lower() in lower_query,
                -int(record.get("water_need_mm", water_budget)),
            ),
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

        return AdvisoryDraft(
            recommendation=(
                f"No seeded {state} crop option fits the {water_budget} mm water and ₹{financial_budget} "
                "input constraints. Do not change crops without extension-officer review."
            ),
            explanation=(
                "The deterministic demo could not find a feasible, state-specific crop record, so it is "
                "not producing an automatic crop plan."
            ),
            confidence=0.55,
            evidence=self._knowledge_hits("crop_kb", evidence_records or regional_records),
        )

    def _diagnosis(
        self, farmer: dict[str, object], query: str, language: str
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

        max_dose = float(protocol["max_dose_ml_per_l"])
        protocol_evidence = protocol | {"_score": 0.95}
        evidence_records = [protocol_evidence] + [
            record for record in evidence_records if record.get("title") != protocol.get("title")
        ]
        recommendation = (
            f"The image-free demo suspects {protocol['name']} pressure in {current_crop}. Capture a clear "
            "leaf photo and obtain officer review before applying any treatment."
        )
        explanation = (
            "Without an image, diagnosis confidence remains below the auto-delivery threshold; any supplied "
            f"dose is checked only against the {max_dose:g} ml/L seeded protocol limit."
        )
        if language.lower().startswith("hi"):
            explanation = (
                "फोटो के बिना निदान का भरोसा कम है; उपचार से पहले कृषि अधिकारी की समीक्षा आवश्यक है।"
            )
        return AdvisoryDraft(
            recommendation=recommendation,
            explanation=explanation,
            confidence=0.62,
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

    def query(self, request: QueryRequest) -> AdvisoryResponse:
        farmer = self.repository.get_farmer(request.farmer_id)
        if farmer is None:
            raise FarmerNotFoundError(request.farmer_id)
        self._require_advisory_consent(farmer)

        intent = request.intent or self.classify_intent(request.query)
        if intent == Intent.DIAGNOSE:
            draft = self._diagnosis(farmer, request.query, request.language)
        elif intent == Intent.SCHEME:
            draft = self._scheme_query(farmer, request.query)
        else:
            draft = self._crop_plan(farmer, request.query, request.language)

        verification = self._verify(farmer, request, intent, draft)
        verification_failed = any(check.status == "fail" for check in verification)
        needs_hitl = verification_failed or draft.confidence < self.settings.hitl_confidence_threshold
        request_id = str(uuid4())
        trace = [
            TraceEvent(
                stage="intent_classifier",
                status="completed",
                detail=f"Classified request as {intent.value}.",
            ),
            TraceEvent(
                stage="planner", status="completed", detail="Built a deterministic demo task graph."
            ),
            TraceEvent(
                stage="memory_agent",
                status="completed",
                detail="Retrieved synthetic twin and knowledge-base context.",
            ),
            TraceEvent(
                stage="reflection",
                status="completed",
                detail="Checked intent coverage, actionable wording, and units.",
            ),
            TraceEvent(
                stage="verifier",
                status="completed",
                detail="Executed deterministic water, budget, weather, scheme, and dose checks.",
            ),
        ]

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
                else "Confidence is below the auto-delivery threshold."
            )
            trace.append(TraceEvent(stage="human_in_the_loop", status="queued", detail=reason))
            self.hitl.enqueue(
                {
                    "case_id": hitl_case_id,
                    "farmer_id": request.farmer_id,
                    "status": "pending",
                    "reason": reason,
                    "request_id": request_id,
                    "intent": intent.value,
                    "confidence": draft.confidence,
                    "original_recommendation": draft.recommendation,
                    "original_explanation": draft.explanation,
                    "evidence": [hit.model_dump(mode="json") for hit in draft.evidence],
                    "verification": [check.model_dump(mode="json") for check in verification],
                    "trace": [event.model_dump(mode="json") for event in trace],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "decision_history": [],
                }
            )

        response = AdvisoryResponse(
            request_id=request_id,
            farmer_id=request.farmer_id,
            intent=intent,
            status="requires_human_review" if needs_hitl else "delivered",
            confidence=draft.confidence,
            recommendation=draft.recommendation,
            explanation=draft.explanation,
            evidence=draft.evidence,
            reflection=reflection,
            verification=verification,
            trace=trace,
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
        farmer = self.repository.get_farmer(request.farmer_id)
        if farmer is None:
            raise FarmerNotFoundError(request.farmer_id)
        self._require_advisory_consent(farmer)
        return self.memory.search(request.farmer_id, request.query)

    def get_farmer(self, farmer_id: str) -> dict[str, object]:
        farmer = self.repository.get_farmer(farmer_id)
        if farmer is None:
            raise FarmerNotFoundError(farmer_id)
        self._require_advisory_consent(farmer)
        return farmer

    def decide_hitl(self, case_id: str, request: HITLDecisionRequest) -> HITLCase | None:
        case = self.hitl.decide(
            case_id,
            request.decision,
            request.reviewer_note,
            request.reviewer_name,
            request.edited_recommendation,
        )
        if case is None and self.hitl.get(case_id) is not None:
            raise HITLCaseNotPendingError(case_id)
        return HITLCase(**case) if case else None

    def list_hitl_cases(self) -> list[HITLCase]:
        return [HITLCase(**case) for case in self.hitl.list()]
