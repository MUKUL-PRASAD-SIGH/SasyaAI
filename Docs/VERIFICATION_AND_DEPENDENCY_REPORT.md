# SasyaAI Verification and Dependency Report

**Reviewed:** 31 July 2026  
**Implementation status:** local production-readiness foundation added; live activation remains human-owned.

## Executive answer

SasyaAI is **built and tested as a local, synthetic-data demonstrator**. It is
**not a complete production agricultural-advisory platform** and should not be
represented as one.

The default running workflow makes **no external API calls**. It reads only
checked-in seed JSON, writes local runtime JSON, and the dashboard calls the
local FastAPI URL by default. No live farmer-data, government, LLM, Lyzr, or
Qdrant API integration is active.

The demonstrator intentionally contains hardcoded/configured demo values and
deterministic rules. These are documented below; they are not hidden live data
or embedded credentials.

## Verification performed

| Check | Result | Evidence |
|---|---|---|
| Backend tests | Pass | `python -m pytest -q` — **27 passed** |
| Backend lint | Pass | `python -m ruff check backend tests` — all checks passed |
| Frontend component tests | Pass | `npm test` — 3 review-safety tests passed |
| Browser end-to-end test | Pass | `npm run test:e2e` — Playwright verified the local API/dashboard hard-safety path |
| Frontend typecheck and production build | Pass | `npm run build` — TypeScript and Vite build succeeded |
| Static external-dependency scan | Reviewed | Searched backend/frontend/configuration for URLs, API-key fields, HTTP clients, Lyzr, and Qdrant references |

Not performed in this verification pass:

- A Docker container runtime smoke test. The local checkout has no `.env` file,
  which is intentionally required by Compose after copying `.env.example`.
- Any live integration test, because this demonstrator deliberately has no
  live external API path or credentials.
- A formal secret-scanning or penetration-testing run.
- Dependency-advisory remediation. The test-tool installation reported two npm
  advisories (one moderate and one high); they need human triage and a
  compatibility-tested upgrade rather than an automatic `--force` change.

## External APIs and network use

### Active default runtime path

No external API is required or called.

- `backend/app/services/advisory.py` uses deterministic Python logic plus the
  checked-in `data/seed/` records.
- `backend/app/services/memory.py` uses local JSON files for advisory memory
  and the HITL queue.
- `backend/app/services/consent.py` uses the local `synthetic_seed` consent
  adapter. It does not perform HTTP requests or use credentials.
- `frontend/src/api.ts` defaults to `http://127.0.0.1:8000`, the local FastAPI
  server. It can be redirected only by explicitly setting
  `VITE_API_BASE_URL`.

### Present but inactive/future-facing configuration

The repository contains placeholders for future integration work:

| Item | Current status |
|---|---|
| `LYZR_API_KEY`, `LYZR_WORKFLOW_ID`, `LYZR_BASE_URL` | Empty/optional configuration; no running code invokes Lyzr |
| `QDRANT_URL`, `QDRANT_API_KEY` and `qdrant-client` | Future retrieval dependency; current code uses lexical seed-JSON retrieval instead |
| Qdrant Docker service | Optional Compose `retrieval` profile; not started by the default `docker compose up --build` path |
| `httpx`, `sentence-transformers` dependencies | Installed project dependencies, but not used for a live external call in the current workflow |

Installing Python/Node dependencies or pulling Docker images can naturally use
package registries/container registries if they are not already cached. That is
build tooling, not a runtime data/API dependency of the demonstrator.

## Hardcoded and seeded values

There are intentional hardcoded/configured values. They are appropriate for a
repeatable synthetic demo, but must be replaced or governed before production.

| Category | Examples | Status |
|---|---|---|
| Synthetic farmer and knowledge data | Names, IDs, districts, crops, water/budget values, consent fixtures, crop/pest/scheme records in `data/seed/` | Intentional; every farmer seed requires `synthetic_data: true` |
| Safety rules | Water/budget checks and seeded pest protocol dose limits | Intentional deterministic controls; require agricultural-domain governance for production |
| Thresholds and local defaults | HITL threshold `0.70`, local CORS origins, default local API URL/ports | Configurable through environment values where applicable; local defaults are intentional |
| Dashboard scenarios | Demo questions and doses in `frontend/src/data.ts` | Intentional UX fixtures |
| Source identity | Consent provider `synthetic_seed` | Explicit local-fixture provenance, not a real provider |

No committed API key, token, or real endpoint credential was found in the
reviewed application/configuration files. This is a static review, not a
substitute for a dedicated secret scanner.

## Safety status

The local demonstrator now enforces the following:

- Typed synthetic consent preflight before farmer-profile or advisory-memory
  access; it fails closed on denied, expired, revoked, malformed, or unavailable
  consent state.
- Validated seed records and atomic, locked local JSON runtime state.
- Deterministic water, budget, weather, scheme, and pesticide checks.
- Failed deterministic checks cannot be overridden by HITL approval or edit;
  the local queue permits only rejection for those cases.
- Low-confidence cases without a failed hard check remain reviewable.

## Local production-readiness additions

- Protected mode (`AUTH_REQUIRED=true`) requires `X-API-Key` authentication,
  role checks, and farmer assignment checks; non-development environments fail
  configuration when protected mode is disabled.
- Protected API actions are limited by an in-process sliding-window limiter and
  generate data-minimised local audit metadata.
- Local advisory/HITL runtime data is pruned by the configured retention window.
  A system-admin deletion route purges those local records and creates a
  `pending_external_cleanup` receipt.
- Safety output and queued cases include `safety_rule_set_version` so an
  approved release can be traced through the local workflow.

## Human-owned production gates

Before any real-user or consequential deployment, the following remain
human-owned activation gates:

- Authenticated and authorised users, role-based review access, and rate limits.
- Live consent receipt verification, revocation cleanup, audit logging, and
  governed retention/deletion workflows.
- Approved, freshness-labelled authoritative agricultural data adapters.
- Domain-reviewed and versioned safety rules plus real evaluation data.
- Durable production data stores, monitoring, incident handling, backups, and
  security testing.

The complete owner/action/evidence list is in
[Production Activation Checklist](PRODUCTION_ACTIVATION_CHECKLIST.md).

## Conclusion

For a local, offline-style synthetic demonstration, the repository is built
and validated with no external runtime API requirement. It is intentionally
deterministic and does contain explicit demo fixtures, local URLs, and safety
rules. Those values are visible and scoped to the demonstrator; they are not a
replacement for production integrations or governance.
