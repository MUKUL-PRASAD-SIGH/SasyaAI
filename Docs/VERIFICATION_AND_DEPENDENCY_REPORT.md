# SasyaAI Verification and Dependency Report

**Reviewed:** 31 July 2026  
**Implementation status:** synthetic production runtime verified locally; live AgriStack mode remains an explicit future switch.

## Executive answer

SasyaAI has a deliberately separated runtime and data-source switch. The
checked-in default is the local synthetic-data `demo` runtime; it makes **no
external API calls** and is not a production advisory service. It reads
checked-in seed JSON and writes local runtime JSON. Production can run with
`PRODUCTION_DATA_MODE=synthetic` for an authenticated, durable pilot, or with
`PRODUCTION_DATA_MODE=live` for the AgriStack path. Synthetic output is for
internal workflow testing only and never for consequential farmer decisions.

The `production` runtime is implemented behind explicit adapters. It uses
separate Gemini calls for schema-constrained routing, specialist drafting, and
reflection, PostgreSQL for durable state,
Qdrant for filtered retrieval, and either labelled synthetic adapters or live
weather/market/AgriStack gateways. It refuses to start without its provider
configuration and authentication, so it cannot silently use the wrong data
source. OTLP export is optional when the deployment scrapes `/metrics`. No live credentials or
source contracts are present in this checkout, therefore production has not
been integration-tested against external providers.

The demonstrator intentionally contains hardcoded/configured demo values and
deterministic rules. These are documented below; they are not hidden live data
or embedded credentials.

## Verification performed

| Check | Result | Evidence |
|---|---|---|
| Backend tests | Pass | `python -m pytest -q` — **41 passed** |
| Backend lint | Pass | `python -m ruff check backend tests scripts` — all checks passed |
| Frontend component tests | Pass | `npm test` — 3 review-safety tests passed |
| Browser end-to-end tests | Assertions pass; Windows runner cleanup flaky | 3 Chromium journeys reached their passing assertions; the local Playwright web-server process did not exit cleanly after completion on this host |
| Frontend typecheck and production build | Pass | `npm run build` — TypeScript and Vite build succeeded |
| Frontend dependency audit | Pass | `npm audit` — 0 vulnerabilities after Vite 8 upgrade |
| Compose and images | Pass | Compose config validated; API (695 MB) and Nginx UI (48.4 MB) images built and returned HTTP 200 in isolated smoke tests |
| Static external-dependency scan | Reviewed | Searched backend/frontend/configuration for URLs, API-key fields, HTTP clients, Lyzr, and Qdrant references |

Not performed in this verification pass:

- A live-provider integration test. No AgriStack/market contracts, production
  database, Qdrant tenant, OTLP collector, or Gemini credential is available in
  this checkout.
- A formal secret-scanning or penetration-testing run.
- Full penetration, load, backup/restore, and disaster-recovery exercises.
- Manual interactive-browser visual inspection. The browser-control surface was
  unavailable; component tests, Chromium assertions, HTTP smoke checks, and
  production image checks passed.

## External APIs and network use

### Active default runtime path

No external API is required or called.

- `backend/app/services/advisory.py` uses deterministic Python logic plus the
  checked-in `data/seed/` records.
- `backend/app/services/memory.py` uses local JSON files for advisory memory
  and the HITL queue.
- `backend/app/services/consent.py` uses the local `synthetic_seed` consent
  adapter. It does not perform HTTP requests or use credentials.
- `frontend/src/api.ts` uses the browser origin by default; local development
  sets `VITE_API_BASE_URL=http://127.0.0.1:8000`, while the container uses the
  same-origin Nginx gateway.

### Production runtime configuration

The repository contains placeholders for future integration work:

| Item | Current status |
|---|---|
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Required in production; the adapter performs typed router, specialist, and reflection calls with bounded retries |
| `DATABASE_URL` | Required PostgreSQL system of record for production profiles, episodes, HITL cases, deletion receipts, and audit events |
| `QDRANT_URL`, `QDRANT_API_KEY` and `qdrant-client` | Required in production for state-filtered semantic retrieval and farmer-scoped vector memory |
| `fastembed==0.8.0` | CPU-only multilingual ONNX embeddings; the 384-dimension model is preloaded into the API image |
| AgriStack and market gateway settings | AgriStack is required only in `PRODUCTION_DATA_MODE=live`; synthetic mode is explicit and internal-only |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional central OTLP trace export; `/metrics` and local instrumentation remain enabled when empty |
| `LYZR_API_KEY`, `LYZR_WORKFLOW_ID`, `LYZR_BASE_URL` | Optional future orchestration configuration; no running code invokes Lyzr |

Installing Python/Node dependencies or pulling Docker images can naturally use
package registries/container registries if they are not already cached. That is
build tooling, not a runtime data/API dependency of demo mode.

## Hardcoded and seeded values

There are intentional hardcoded/configured values. They are appropriate for a
repeatable synthetic demo, but must be replaced or governed before production.

| Category | Examples | Status |
|---|---|---|
| Synthetic farmer and knowledge data | 18 non-real profiles and 105 crop/pest/scheme references in `data/seed/` | Available in demo and explicit synthetic production mode; every record remains labelled `synthetic_reference` |
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

- A nine-role agent registry and safe per-agent execution telemetry expose
  model/tool/deterministic boundaries without exposing private reasoning.
- A versioned 18-state evaluation corpus is generated deterministically with
  provenance fields and an explicit dataset card.
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
- The operations UI has field/night themes, runtime and knowledge telemetry,
  the expanded evaluation cohort, agent runs, and a memory-only internal
  operator credential input.
- Docker Compose now includes the Nginx-served UI with API proxying and health
  checks in addition to the API, PostgreSQL, and Qdrant.

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

The repository now has a real provider-backed production execution path and a
clearly labelled deterministic evaluation fallback. Local behavior is built
and tested without external credentials. Production activation remains blocked
until the startup supplies and validates real provider contracts, governed
agronomy content, identity infrastructure, and the human-owned launch evidence
listed above.
