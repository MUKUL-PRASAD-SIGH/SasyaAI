# SasyaAI API Reference

Base URL for local development: `http://127.0.0.1:8000`.

Demo mode operates only on checked-in synthetic data. Production mode uses
live provider adapters and durable stores. In development the API uses an
explicit local bypass. When `AUTH_REQUIRED=true`, all `/api/v1/*`
routes require an `X-API-Key` configured through `AUTH_PRINCIPALS_JSON`; roles
and farmer assignments are enforced, protected actions are rate-limited, and
data-minimised audit metadata is retained locally. This API-key adapter is a
testable gateway boundary, not a replacement for production OAuth2/OIDC/JWT.

## Implemented endpoint groups

The current API surface includes:

- auth endpoints for login, logout, Google-demo login, and session inspection
- advisory endpoints for query submission and knowledge stats
- farmer lifecycle endpoints for registration, image upload/listing, feedback, profile retrieval, and runtime-data deletion
- HITL endpoints for listing review cases and recording a decision
- audit and runtime endpoints for health and admin visibility

The sections below capture the implemented contract and the guarded production-only extensions.

## Conventions

- JSON request and response bodies use UTF-8.
- `400` indicates malformed content, `401` invalid/missing authentication in protected mode, `403` insufficient role/assignment or invalid advisory consent, `404` an unknown demo resource, `422` a schema-validation failure, `429` a rate-limit response, and `503` a local state or consent-adapter failure that is blocked from delivery.
- Advisory response `status` is either `delivered` or `requires_human_review`.
- A response is never auto-delivered when a verification check fails or confidence is below `0.70`.
- Every advisory and queued case carries the configured `safety_rule_set_version` for review traceability.

## Local protected-mode configuration

Set `AUTH_REQUIRED=true` and provide `AUTH_PRINCIPALS_JSON` only from a secret
manager. It is a JSON array of API-key records with `subject`, `roles`, and
`allowed_farmer_ids`; never commit it or compile a key into the dashboard.
The internal operations UI accepts a role-scoped key into memory only and
clears it on reload.

Example shape (use a generated secret-manager value, never this literal key):

```json
[{"api_key":"replace-with-a-32-byte-secret","subject":"ops-admin","roles":["system_admin"],"allowed_farmer_ids":null}]
```
The allowed roles are `farmer`, `extension_officer`, and `system_admin` for
the currently implemented protected endpoints. Replace this adapter with an
approved OIDC/JWT gateway before production.

## `GET /health`

Returns service health without exposing dependencies or configuration.

```json
{
  "status": "ok",
  "service": "SasyaAI",
  "environment": "development",
  "runtime_mode": "demo",
  "data_source_mode": "synthetic",
  "agent_execution": "deterministic_fallback"
}
```

In production, `data_source_mode` is `synthetic` or `live`. Synthetic mode is
explicitly review-only; the live mode is the AgriStack-ready contract.

## `GET /api/v1/agents`

Returns the governed nine-role registry, responsibility boundaries, production
model label, and the single permitted memory writer.

## `GET /api/v1/knowledge/stats`

Returns collection counts and region/crop coverage without source content or
farmer PII.

## `GET /api/v1/demo/farmers`

Returns non-sensitive summaries for the 18-profile synthetic evaluation cohort.
The summary includes current crop, season, farm size, soil type and fertility,
irrigation type, water budget, input budget, language, state, and district so
the role-scoped Profile view can reflect the farmer's registered context.
It returns `404` in production so real farmers cannot be enumerated.

## `POST /api/v1/query`

Checks consent before any profile read, runs the selected runtime's typed agent
graph, appends an episode through the Memory boundary, and either returns
verified advice or creates an HITL case.

Request:

```json
{
  "farmer_id": "AGR_MH_001234",
  "query": "Should I switch from cotton to soybean?",
  "intent": "crop_plan_request",
  "language": "mr",
  "requested_dose_ml_per_l": 1.5
}
```

`intent` and `requested_dose_ml_per_l` are optional. Supported intents are `crop_plan_request`, `diagnose`, and `scheme_query`.

Delivered response excerpt:

```json
{
  "request_id": "uuid",
  "farmer_id": "AGR_MH_001234",
  "intent": "crop_plan_request",
  "status": "delivered",
  "confidence": 0.84,
  "recommendation": "Choose soybean for the coming Kharif season...",
  "explanation": "पाण्याची उपलब्धता...",
  "evidence": [{"source": "crop_kb", "title": "Soybean suitability...", "score": 0.75}],
  "reflection": {"status": "pass", "notes": ["Response addresses the requested intent."]},
  "verification": [{"name": "water_budget", "status": "pass", "message": "..."}],
  "agent_runs": [{
    "agent_id": "safety_verifier",
    "execution_mode": "deterministic",
    "duration_ms": 1,
    "summary": "Applied non-LLM delivery gates."
  }],
  "trace": [{"stage": "verifier", "status": "completed", "detail": "..."}],
  "hitl_case_id": null
}
```

When advice requires review, `status` is `requires_human_review` and `hitl_case_id` is populated. Client applications must show review-pending state, never present it as final advice.

## `GET /api/v1/farmers/{farmer_id}`

Returns a synthetic farmer twin for the demo only after a consent preflight.
Example IDs include:

- `AGR_MH_001234`
- `AGR_TG_005678`
- `AGR_KA_009012`

The full demo cohort is discoverable only through `/api/v1/demo/farmers`.
Production returns only fields authorised by caller role, consent, purpose, and
assignment; sensitive fields must be masked or omitted by default.

## `POST /api/v1/memory/search`

Checks consent before searching runtime advisory episodes for a farmer. The API retains the `farmer_id` filter as an invariant; production Qdrant search must do the same.

```json
{
  "farmer_id": "AGR_MH_001234",
  "query": "soybean"
}
```

## `GET /api/v1/hitl`

Lists local review cases, newest first. A case includes the original draft,
confidence, evidence, deterministic verification results, workflow trace, and
append-only decision history so an extension officer can review the complete
demo context.

If any deterministic verification status is `fail`, the local demonstrator
allows only `reject`; `approve` and `edit_and_approve` return `409`. An officer
must start a fresh, safely parameterised request rather than override a hard
safety check.

In protected mode this endpoint is restricted to `extension_officer` and
`system_admin`; a non-admin receives only cases for assigned farmer IDs.

## `POST /api/v1/hitl/{case_id}/decision`

Records an extension-officer decision for a pending case.

For a case with a failed deterministic check, only `reject` is accepted.

```json
{
  "decision": "edit_and_approve",
  "reviewer_name": "R. Kulkarni",
  "reviewer_note": "Reduce the input recommendation and confirm local rainfall.",
  "edited_recommendation": "Use the officer-approved revised plan."
}
```

`decision` is one of `approve`, `edit_and_approve`, or `reject`. An
`edit_and_approve` decision requires `edited_recommendation`. The local demo
records reviewer name, note, timestamp, original draft, and an append-only
decision history. Once a case has a decision, a later decision returns `409`;
the original decision cannot be overwritten.

Production must additionally enforce reviewer authentication, assignment,
evidence-view audit events, durable immutable storage, and retention policy.

## `GET /api/v1/audit`

Returns data-minimised local audit metadata to `system_admin` callers in
protected mode. It never records question text, consent payloads, or API keys.
Production must export the same event contract to durable, access-controlled
audit infrastructure.

## `DELETE /api/v1/farmers/{farmer_id}/runtime-data`

Restricted to `system_admin` in protected mode. It purges local advisory-memory
and HITL runtime records, then creates a `pending_external_cleanup` receipt.
Checked-in synthetic seed fixtures deliberately remain immutable. A human must
complete and evidence deletion with every real provider, backup, and retention
owner before closing a production request.

## Production-only operations

- `POST /api/v1/farmers/{farmer_id}/sync` refreshes a consent-gated AgriStack
  profile into PostgreSQL.
- `POST /api/v1/knowledge/documents` ingests a reviewer-attributed document
  into a governed Qdrant collection.

Both return `404` in demo mode and require appropriate roles.

## Planned API surface

| Endpoint family | Purpose | Prerequisite |
|---|---|---|
| `/api/v1/consents` | Create, view, revoke farmer consent | AgriStack Sandbox integration |
| `/api/v1/land-parcels` | Consent-gated parcel and geospatial data | Land adapter + PostGIS |
| `/api/v1/images` | Image upload and diagnosis job | Virus/file validation + vision pipeline |
| `/api/v1/alerts` | Farmer/region alerts and acknowledgements | Monitoring event pipeline |
| `/api/v1/twins` | Versioned twin access/export/delete | Auth, consent, DSAR workflows |
| `/api/v1/admin/rules` | Rule versions and controlled rollout | RBAC, domain review, audit |

No planned write endpoint may bypass the Memory Agent, audit boundary, or consent check.
