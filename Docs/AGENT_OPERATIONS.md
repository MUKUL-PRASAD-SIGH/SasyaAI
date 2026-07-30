# Agent operations and governance

## Execution model

SasyaAI uses a typed workflow, not an open-ended agent swarm. The Root Manager
owns the request budget and selects the minimum graph. In production, Gemini
performs three separate schema-constrained calls: routing, specialist drafting,
and reflection. Retrieval, live-provider calls, persistence, consent checks,
and the final safety decision stay outside the model.

```text
request
  -> live consent + authorised farmer refresh
  -> Intent Router (LLM) -> typed TaskGraph
  -> Live Data Agent (tools) + Memory Agent (Qdrant)
  -> one domain specialist (LLM)
  -> Reflection Agent (LLM, one bounded revision)
  -> Safety Verifier (deterministic)
  -> deliver OR durable human-review case
  -> PostgreSQL episode + farmer-scoped Qdrant memory
```

Demo mode runs the same public contract with deterministic specialists and
versioned synthetic files. It is an explicit evaluation fallback, never a
silent production fallback.

## Role boundaries

| Agent | Production execution | Authority |
| --- | --- | --- |
| Root Manager | Deterministic coordinator | Starts and bounds the typed graph |
| Intent Router | Gemini | Chooses one specialist and required sources |
| Crop Planning Agent | Gemini | Drafts crop/resource guidance from supplied facts |
| Pest Diagnosis Agent | Gemini | Drafts cautious observation and escalation guidance |
| Scheme Navigation Agent | Gemini | Explains evidence and official verification steps |
| Live Data Agent | HTTP tools | Reads AgriStack, Open-Meteo, and market snapshots |
| Memory Agent | PostgreSQL/Qdrant tools | Sole read/write owner for durable memory |
| Reflection Agent | Gemini | Checks and optionally revises within existing evidence |
| Safety Verifier | Deterministic policy | Controls delivery; no model can override it |

Only the Memory Agent can write episodic memory. A failed deterministic check
cannot be approved by a reviewer.

## Model contracts

Every LLM response is validated against a Pydantic-generated JSON schema.
Invalid JSON, unsupported enum values, missing required fields, retry
exhaustion, or an open circuit fails the request with no production fallback.
An explicit API intent overrides a conflicting router classification.

The specialist may cite only evidence identifiers supplied in its prompt.
Reflection may reduce confidence and revise wording, but cannot add a source,
number, treatment, eligibility claim, or fact. The verifier rejects citations
that do not map to retrieved evidence and rejects model-authored pesticide
dosages.

## Operational telemetry

Responses and review cases include `agent_runs`. This is safe execution
telemetry:

- stable agent identifier and role;
- execution mode and configured model label;
- status, elapsed milliseconds, and output confidence;
- named input sources; and
- a short operational result.

It deliberately excludes prompts, secrets, farmer PII, consent payloads, and
private chain-of-thought. OpenTelemetry spans contain route/status metadata
only. Prometheus metrics are mounted in production.

## Failure policy

- Missing production configuration prevents startup.
- Unavailable live data, LLM, Qdrant, or PostgreSQL returns a service failure;
  seed data is never substituted.
- Required but incomplete weather data fails the deterministic weather gate.
- Missing grounding, unsafe weather, or dosage specificity creates a blocked
  human-review case.
- Low confidence or a model escalation flag creates a review case.
- PostgreSQL is the episodic system of record. A failed vector-memory write is
  queued for retry and disclosed in the trace.

Production knowledge can be streamed from reviewer-approved JSONL through
`scripts/ingest_reviewed_corpus.py`. Stable identifiers make reruns idempotent;
the API still enforces system-admin access and source/reviewer metadata.

## Launch evaluation

Before serving real users, run a versioned evaluation set with domain-reviewed
expected outcomes for every supported state/crop/language combination. Measure
routing accuracy, citation precision, abstention, unsafe-advice rate, connector
freshness, latency, and reviewer disagreement. The synthetic corpus is useful
for contract regression but does not satisfy agronomic validation.
