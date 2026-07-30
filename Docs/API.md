# SasyaAI API Reference

Base URL for local development: `http://127.0.0.1:8000`.

The local API operates only on checked-in synthetic data. It has no authentication because it is not a production deployment. Production endpoints will require OAuth2/JWT, scope checks, consent verification, rate limiting, request IDs, audit logging, and versioned deprecation policy.

## Conventions

- JSON request and response bodies use UTF-8.
- `400` indicates malformed content, `403` indicates consent is not currently valid for the requested advisory use, `404` indicates an unknown demo resource, `422` indicates a schema-validation failure, and `503` indicates a local state or consent-adapter failure that is blocked from delivery.
- Advisory response `status` is either `delivered` or `requires_human_review`.
- A response is never auto-delivered when a verification check fails or confidence is below `0.70`.

## `GET /health`

Returns service health without exposing dependencies or configuration.

```json
{
  "status": "ok",
  "service": "SasyaAI",
  "environment": "development"
}
```

## `POST /api/v1/query`

Checks a typed synthetic consent fixture before any profile read, then classifies the request, retrieves demo context, runs reflection and hard checks, appends an episode through the Memory boundary, and either returns advice or creates an HITL case. The consent result records static-fixture provenance internally; it does not call a live provider.

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
  "trace": [{"stage": "verifier", "status": "completed", "detail": "..."}],
  "hitl_case_id": null
}
```

When advice requires review, `status` is `requires_human_review` and `hitl_case_id` is populated. Client applications must show review-pending state, never present it as final advice.

## `GET /api/v1/farmers/{farmer_id}`

Returns a synthetic farmer twin for the demo only after a consent preflight. Example IDs:

- `AGR_MH_001234`
- `AGR_TG_005678`
- `AGR_KA_009012`

Production equivalent: return only fields authorised by caller role, consent, purpose, and assignment; sensitive fields must be masked or omitted by default.

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

This is an unauthenticated synthetic-data demonstration endpoint. Production
must scope cases to an assigned, authorised reviewer.

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
