# SasyaAI

SasyaAI is a safety-gated agricultural-advisory platform for Indian farmers. It combines a farmer digital twin, grounded knowledge retrieval, specialised agent workflows, deterministic verification, and human review to produce practical, explainable guidance.

This repository has two explicitly separated runtimes:

- `RUNTIME_MODE=demo` is a credential-free local workflow over synthetic seed data. It exists for contract development and must not be presented as a live advisory service.
- `RUNTIME_MODE=production` is the startup path: Gemini plans and drafts grounded advice, PostgreSQL owns farmer/HITL/audit state, Qdrant retrieves governed knowledge, and live AgriStack, weather, and market adapters supply source-attributed context. It refuses to boot until its credentials, durable stores, authentication, and live-provider contracts are configured; OTLP export is optional because `/metrics` remains available locally.

## What works today

- FastAPI service with runtime health, agent registry, knowledge coverage, advisory, farmer, memory, and HITL endpoints.
- A typed nine-role agent graph with separate production LLM calls for routing, one domain specialist, and reflection.
- A deterministic 105-record evaluation corpus spanning 18 states and 20 crops, plus 18 synthetic farmers.
- Memory ownership boundary, typed consent preflight, state-filtered retrieval, reflection, deterministic safety checks, and confidence-based HITL routing.
- Local production-readiness controls: API-key authentication/RBAC when enabled, farmer assignment checks, in-process rate limits, data-minimised audit events, runtime retention, and governed local deletion requests.
- Themeable Vite/React operations cockpit for reviewing agent runs, source evidence, verification, traces, and pending cases.
- Backend, model-contract, component, and browser end-to-end regression suites.
- Docker Compose for the operations UI, API, PostgreSQL, and Qdrant.
- Tests for delivered advice, low-confidence escalation, unsafe-dose blocking, and API errors.

## Production runtime

The production workflow is implemented behind provider boundaries so the model and official-data connectors can evolve without rewriting safety logic. Gemini is the initial LLM provider because it offers a limited free development tier, multilingual capability, and JSON output; production capacity must still be funded and rate-limited. It is never a source of truth: live data and Qdrant evidence are supplied to it, then deterministic gates enforce grounding, weather risk, and pesticide-dose policy before a response can be delivered.

Before using `RUNTIME_MODE=production`, follow [Production Runtime](Docs/PRODUCTION_RUNTIME.md). The startup team must obtain approved AgriStack and market gateway contracts, populate governed PostgreSQL/Qdrant data, configure OIDC or the temporary backend credentials, and set the required secrets through a secret manager. A missing dependency prevents startup rather than silently using seed data.

## Quick start

Prerequisites: Python 3.10+ and Docker Desktop for the container route. Node.js 22+ is needed only for local frontend development.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `/docs`.

```powershell
python -m pytest -q
python -m ruff check backend tests scripts
```

To run the self-contained API container:

```powershell
docker compose up --build
```

Compose starts the operations UI at `http://127.0.0.1:5173`, the API at
`http://127.0.0.1:8000`, PostgreSQL, and Qdrant. The durable stores remain
unused while `RUNTIME_MODE=demo` is selected.

### Extension-officer dashboard

Run the API first, then start the separate local dashboard in another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm test
npm run dev
```

Open `http://127.0.0.1:5173`. The development environment points the dashboard
to `http://127.0.0.1:8000`; the container build uses the same-origin Nginx
gateway. In production mode an operator can supply a role-scoped API key that
is held in browser memory only and cleared on reload. A public deployment
should place OIDC and a backend-for-frontend gateway in front of the API.

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
scripts/        Deterministic evaluation-corpus tooling
tests/          API and workflow regression tests
```

The planned `infra/` and `ml/` areas belong to later cloud and vision work.

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
- [Production Runtime](Docs/PRODUCTION_RUNTIME.md)
- [Agent Operations](Docs/AGENT_OPERATIONS.md)
- [Evaluation Corpus Card](data/seed/DATASET_CARD.md)
- [Production Activation Checklist](Docs/PRODUCTION_ACTIVATION_CHECKLIST.md)

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Contributions that affect recommendations, safety rules, data access, or consent flows require domain and security review.
