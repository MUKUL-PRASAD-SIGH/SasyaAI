# SasyaAI Requirements

## 1. Product goal

Enable Indian farmers and extension officers to receive hyperlocal agricultural guidance that is personalised to a farmer's land and constraints, grounded in traceable data, checked against non-negotiable rules, and explainable in the farmer's language.

## 2. Scope

### In scope for the demonstrator

- Crop-plan, pest-diagnosis, and scheme-eligibility intents.
- Synthetic farmer twins and curated crop, pest, and scheme knowledge.
- Structured advisory response with evidence, reflection, verifier results, and execution trace.
- Water, financial, weather, scheme, and pesticide-dose gates.
- Confidence-based extension-officer queue.

### Explicitly out of scope for the demonstrator

- Real farmer records, production AgriStack access, and real scheme-enrolment submission.
- Diagnostic claims from actual photos, trained CV models, or medical/pesticide instructions beyond a safe mocked protocol.
- Production authentication, payments, voice telephony, offline synchronisation, and mobile release.
- Production availability, scale, DPDP operational compliance, or public data residency certification.

## 3. Stakeholders and needs

| Stakeholder | Need | Success signal |
|---|---|---|
| Farmer | Simple, actionable, language-appropriate guidance | Understands the next safe action and why |
| Extension officer | Fast review with evidence and editable draft | Can approve, amend, or reject without recreating context |
| Agricultural domain expert | Control over advice and safety rules | Rules and knowledge have source, version, and owner |
| Platform operator | Observable, maintainable services | Clear failures, audit trail, and reversible deployments |
| Government/data partner | Consent-respecting, purpose-limited data use | Sandbox tests and documented data governance |

## 4. Functional requirements

| ID | Requirement | Demo acceptance criterion | Production evolution |
|---|---|---|---|
| FR-001 | Maintain a farmer twin keyed by farmer ID | Three synthetic twins are retrievable | Versioned PostgreSQL/PostGIS model |
| FR-002 | Read consent before data use | Synthetic consent field is checked before live integration work | AgriStack consent preflight and revocation support |
| FR-010 | Classify advice intent | Three supported intents route predictably | Multilingual classifier with evaluation set |
| FR-011 | Produce a typed task graph | Trace records routing and stages | ADK/Lyzr execution graph with timeouts and retries |
| FR-020 | Retrieve knowledge with scope filters | Response includes relevant seed evidence | Qdrant hybrid search and freshness/version metadata |
| FR-021 | Keep persistence behind one owner | Only Memory service writes runtime episodes | Memory Agent owns Qdrant/twin writes |
| FR-030 | Plan crop recommendations | Cotton-to-soybean request returns contextual result | OR-Tools feasibility and Pareto ranking |
| FR-031 | Diagnose pest/disease safely | Image-free diagnosis is routed to review | Validated vision model with confidence calibration |
| FR-032 | Check scheme information | Response states live confirmation is required | Authoritative scheme adapter and rule versioning |
| FR-040 | Reflect on draft quality | Response includes structured reflection | Evaluated prompt/versioned rubric |
| FR-041 | Verify consequential advice | Unsafe 3 ml/L dose is blocked | Complete constraint catalogue and rule audit |
| FR-042 | Escalate uncertainty | Confidence under 0.70 creates HITL case | Authenticated review dashboard and SLA tracking |
| FR-050 | Explain advice | Response contains plain-language explanation and evidence | Local-language, voice, and visual explanation |
| FR-060 | Retain auditable decisions | Runtime trace and episode are recorded | Immutable audit logs and export support |

## 5. Non-functional requirements

| Category | Target | Measurement |
|---|---|---|
| Safety | 100% of consequential outputs pass verifier or reach HITL | Workflow and regression tests |
| Latency | Demo and task-graph P95 under 20 seconds | Traced request duration |
| API responsiveness | Standard read P95 under 2 seconds | API metrics |
| Availability | Production target 99.5% | Synthetic checks and SLO dashboard |
| Data freshness | Weather 15 min, market 30 min, satellite 48 hr | Source metadata and freshness alerts |
| Privacy | No stored Aadhaar; consent and least privilege enforced | Security review and audit checks |
| Explainability | Every delivered recommendation has evidence and a reason | Response-schema validation |
| Accessibility | Hindi plus regional languages and voice roadmap | Usability tests with target users |
| Offline | Cached advice and on-device diagnosis roadmap | Mobile integration tests |

## 6. Constraints and assumptions

### Assumptions

- The initial team has five roles: AI architecture, backend/data, computer vision, full-stack UX, and agricultural domain expertise.
- Sandbox data is synthetic and may not represent production API shape or data quality.
- Official data sources and scheme rules can change; advice must expose freshness and source status.
- A qualified agricultural reviewer is available for safety-sensitive or low-confidence decisions.

### Constraints

- Do not use live farmer data until consent, sandbox, security, and governance gates are complete.
- Demo success favours transparent deterministic mocks over unreliable third-party calls.
- Pesticide, finance, and scheme advice require deterministic validation; an LLM alone is never sufficient.
- PII must remain in India for production and must be minimised throughout the pipeline.

## 7. Risks and mitigations

| Risk | Mitigation | Owner |
|---|---|---|
| Incorrect or stale advice | Source freshness, hard verifier, HITL | Domain expert + backend |
| Hallucinated claims | Grounded retrieval and constrained response schema | AI architect |
| Tool outage/latency | Timeout, fallback, degraded confidence | Backend/data |
| Poor image quality | Image-quality gate and human escalation | CV engineer |
| Low farmer trust | Explain-by-default UX and officer review label | UX + domain |
| PII exposure | Consent, RBAC, encryption, audit, secret management | Security owner |
| Scope expansion | Phase gates and acceptance criteria | Project lead |

## 8. Definition of done

A milestone is complete only when its functionality, tests, documentation, data handling, safety constraints, and operational checks are all accepted. A polished UI or successful demo does not substitute for a passing verifier path and documented limitations.
