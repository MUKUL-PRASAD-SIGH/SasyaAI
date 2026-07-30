# SasyaAI

SasyaAI is a safety-gated agricultural-advisory platform for Indian farmers. It combines a farmer digital twin, grounded knowledge retrieval, specialised agent workflows, deterministic verification, and human review to produce practical, explainable guidance.

This repository starts with a runnable synthetic-data demonstrator. It is deliberately credential-free and deterministic so the team can validate the workflow before connecting real farmer data, LLMs, or government APIs.

## What works today

- FastAPI service with health, advisory, farmer, memory, and HITL queue/decision endpoints.
- Three synthetic farmers plus crop, pest, and scheme seed knowledge.
- Intent routing for crop planning, pest diagnosis, and scheme queries.
- Memory ownership boundary, typed synthetic-consent preflight with purpose/scope/expiry/revocation checks, reflection results, data-driven deterministic safety checks, and a confidence-based HITL route.
- Local production-readiness controls: API-key authentication/RBAC when enabled, farmer assignment checks, in-process rate limits, data-minimised audit events, runtime retention, and governed local deletion requests.
- Vite/React extension-officer dashboard for reviewing evidence, verification, trace, and pending cases.
- Backend, component, and browser end-to-end regression suites for the supported demonstrator flow.
- Docker Compose for the API and optional local Qdrant service.
- Tests for delivered advice, low-confidence escalation, unsafe-dose blocking, and API errors.

## What is planned next

The current service is a local workflow, not a production advisory system. Qdrant retrieval, Lyzr/ADK execution, AgriStack Sandbox adapters, PostgreSQL/PostGIS, real vision models, and the farmer/mobile experience are sequenced in [Docs/ROADMAP.md](Docs/ROADMAP.md).

The local API deliberately starts in development-bypass mode. Before any non-local deployment, enable `AUTH_REQUIRED=true`, inject API credentials through a secret manager, and complete the human-owned gates in [Production Activation Checklist](Docs/PRODUCTION_ACTIVATION_CHECKLIST.md). Do not put an API key in a browser `VITE_*` variable.

## Quick start

Prerequisites: Python 3.10+ and Docker Desktop for the container route. Node.js 20+ is needed only for the frontend scaffold.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

```powershell
python -m pytest -q
python -m ruff check backend tests
```

To run the self-contained API container:

```powershell
docker compose up --build
```

The current workflow does not query Qdrant. To include the optional local
Qdrant container for retrieval experiments, use
`docker compose --profile retrieval up --build`.

### Extension-officer dashboard

Run the API first, then start the separate local dashboard in another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm test
npm run dev
```

Open `http://127.0.0.1:5173`. The dashboard defaults to the local API at
`http://127.0.0.1:8000`; change `VITE_API_BASE_URL` in `frontend/.env` only when
using a different endpoint. It deliberately labels review-pending advice as a
draft and records an append-only demo decision history for each case.

To run the local browser test after installing its Chromium test dependency:

```powershell
npx playwright install chromium
npm run test:e2e
```

### Example request

```powershell
$body = @{
  farmer_id = "AGR_MH_001234"
  query = "Should I switch from cotton to soybean?"
  language = "mr"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/query `
  -ContentType "application/json" -Body $body
```

## Repository layout

```text
backend/        FastAPI application, contracts, workflow, and adapters
data/seed/      Checked-in synthetic demo farmers and knowledge bases
Docs/           Product, architecture, API, execution, security, and testing docs
frontend/       Vite/React extension-officer dashboard
tests/          API and workflow regression tests
```

The planned `infra/`, `ml/`, and `scripts/` areas are intentionally not yet
created; they belong to later sandbox, vision, and production-hardening work.

## Safety and data use

The seed records are synthetic. Do not add real farmer data, credentials, Aadhaar numbers, or production exports to this repository. Before any demonstrator profile or advisory-memory access, a local fixture adapter checks a typed consent receipt and carries source/freshness provenance internally. It is deliberately not a live consent-management integration. A failed deterministic safety check cannot be overridden by approving or editing its HITL case; the local workflow permits rejection and a fresh, safely parameterised request only. The service must remain behind consent, deterministic verification, and Human-in-the-Loop gates before it can be used for consequential advice.

## Project documentation

- [Master Plan](Docs/MASTER_PLAN.md)
- [Architecture](Docs/ARCHITECTURE.md)
- [Requirements](Docs/REQUIREMENTS.md)
- [Execution Roadmap](Docs/ROADMAP.md)
- [API Reference](Docs/API.md)
- [Testing Strategy](Docs/TESTING.md)
- [Deployment Guide](Docs/DEPLOYMENT.md)
- [Security and Privacy](Docs/SECURITY.md)
- [Development Guide](Docs/DEVELOPMENT.md)
- [Verification and Dependency Report](Docs/VERIFICATION_AND_DEPENDENCY_REPORT.md)
- [Production Activation Checklist](Docs/PRODUCTION_ACTIVATION_CHECKLIST.md)

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Contributions that affect recommendations, safety rules, data access, or consent flows require domain and security review.
