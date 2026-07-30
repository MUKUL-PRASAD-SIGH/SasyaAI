# SasyaAI Production Runtime

`RUNTIME_MODE=production` is the provider-backed startup runtime. It never
falls back to seed JSON or local runtime files. A missing or unavailable
dependency returns a controlled `503` without delivering an advisory.

## Implemented request path

```text
Live AgriStack consent preflight
  -> PostgreSQL farmer twin
  -> AgriStack + Open-Meteo + market tool reads
  -> filtered Qdrant retrieval
  -> Gemini JSON plan and farmer-facing draft
  -> deterministic grounding / weather / dose verifier
  -> deliver, or queue durable HITL case
  -> PostgreSQL episode + farmer-scoped Qdrant memory
```

The LLM is intentionally not an authority for facts, eligibility, dosage, or
safety policy. It receives only minimised farmer context and retrieved source
facts. It must return typed JSON and cite retrieved evidence IDs. A missing
citation, severe live-weather signal, or LLM-generated pesticide dose blocks
automatic delivery.

## Initial LLM choice

The first adapter is the Gemini Developer API (`gemini-2.5-flash` by default).
It is a sensible development launch choice for Hindi/Marathi support, low
latency, and structured JSON output, and Google provides a limited free tier
for experimentation. Free quota is not a production capacity plan: establish a
budget, quota alerts, and a paid account before onboarding farmers. The
provider interface in `backend/app/services/llm.py` makes a Vertex, OpenAI, or
self-hosted replacement a contained change.

## Required configuration

Production startup checks these settings before the web server is created:

- `AUTH_REQUIRED=true` and an injected credential source;
- `GEMINI_API_KEY`;
- `DATABASE_URL` pointing to PostgreSQL;
- `QDRANT_URL` (and `QDRANT_API_KEY` where applicable);
- AgriStack gateway URL/token;
- approved market-provider URL/key;
- an OTLP tracing endpoint.

Copy `.env.example` only for local configuration. In staging and production,
put the values in a secret manager or workload identity system. Do not expose
any of these values via the browser or commit a populated `.env` file.

## Gateway contracts to approve before launch

AgriStack catalogue access is tenant- and approval-specific, so this repository
does not invent a government API specification. The gateway serving this app
must provide these canonical JSON contracts, authenticate upstream with its
approved client identity, and retain the original source receipt for audit:

```text
GET {AGRISTACK_API_BASE_URL}/consents/{farmer_id}?purpose=agricultural_advisory
Authorization: Bearer {AGRISTACK_ACCESS_TOKEN}

{
  "consent_id": "...", "status": "granted",
  "purpose": "agricultural_advisory",
  "scopes": ["farmer_profile", "advisory", "advisory_memory"],
  "granted_at": "RFC3339", "expires_at": "RFC3339 or null",
  "revoked_at": null, "source_record_id": "...", "updated_at": "RFC3339"
}
```

```text
GET {AGRISTACK_API_BASE_URL}/farmers/{farmer_id}/context
Authorization: Bearer {AGRISTACK_ACCESS_TOKEN}

{
  "farmer_id": "...", "state": "...", "district": "...",
  "preferred_language": "mr",
  "location": {"latitude": 19.99, "longitude": 78.12},
  "digital_twin": {"season": "Kharif", "current_crop": "...", "...": "..."}
}
```

The context endpoint is source-attributed but is not passed wholesale to the
LLM. Add and validate only the decision fields required by a tool. The market
gateway is called with `district`, current `crop`, and a bounded query string;
it must return a JSON object containing provenance and timestamped market facts.
Replace these gateway adapters only after validating the exact sandbox/OpenAPI
contract supplied to your registered organisation.

Every advisory refreshes the authorised farmer context from this endpoint and
persists the validated copy to PostgreSQL. `POST /api/v1/farmers/{farmer_id}/sync`
provides the same consent-gated refresh for onboarding and operational checks.

## Data ownership

PostgreSQL is the system of record for farmer profiles, consent snapshots,
advisory episodes, HITL cases, audit events, and deletion receipts. Qdrant is
the source for governed semantic documents and farmer-filtered vector memory.
Before accepting traffic, ingest reviewed knowledge with a `document_id`,
`title`, source/freshness metadata, and mandatory `state` payload value—the
production retriever uses the state filter rather than cross-region fallback.

Use `POST /api/v1/knowledge/documents` with a system-admin identity to ingest a
reviewed document. The API requires its source URL, source-updated timestamp,
state, and reviewer identity and is disabled in demo mode. It is an ingestion
boundary, not a web-scraper: only content that has passed agronomy and source
governance review belongs in Qdrant.

Farmer profile ingestion must happen behind an authenticated service boundary.
The production profile needs at least `farmer_id`, `state`, `district`,
`preferred_language`, a `digital_twin` object, and an authorised `location`
object with `latitude`/`longitude` for live weather. Never store Aadhaar values.

## Local infrastructure smoke path

```powershell
Copy-Item .env.example .env
docker compose up --build
```

This starts PostgreSQL and Qdrant, but remains in demo mode by default. For a
staging environment, supply secrets outside the repository, set
`RUNTIME_MODE=production`, and populate all required provider values. Do not
switch that flag until the provider contracts, source validation, and security
review above are complete.

## Remaining launch gates

The code creates the production execution boundary; it cannot itself obtain
government credentials, approve a market-data contract, provide a legal basis
for PII processing, or certify agronomic rules. Those are organisation-owned
launch gates. Complete the security, domain-review, load-test, backup/restore,
incident-response, and OIDC/distributed-rate-limit work in the Production
Activation Checklist before serving real farmers.
