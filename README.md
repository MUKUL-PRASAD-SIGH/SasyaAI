# SasyaAI

SasyaAI is a safety-gated agricultural-advisory platform for Indian farmers. It combines a farmer digital twin, grounded knowledge retrieval, specialised agent workflows, deterministic verification, and human review to produce practical, explainable guidance.

This repository starts with a runnable synthetic-data demonstrator. It is deliberately credential-free and deterministic so the team can validate the workflow before connecting real farmer data, LLMs, or government APIs.

## What works today

- FastAPI service with health, advisory, farmer, memory, and HITL queue/decision endpoints.
- Three synthetic farmers plus crop, pest, and scheme seed knowledge.
- Intent routing for crop planning, pest diagnosis, and scheme queries.
- Memory ownership boundary, consent preflight, reflection results, data-driven deterministic safety checks, and a confidence-based HITL route.
- Vite/React extension-officer dashboard for reviewing evidence, verification, trace, and pending cases.
- Docker Compose for the API and optional local Qdrant service.
- Tests for delivered advice, low-confidence escalation, unsafe-dose blocking, and API errors.

## What is planned next

The current service is a local workflow, not a production advisory system. Qdrant retrieval, Lyzr/ADK execution, AgriStack Sandbox adapters, PostgreSQL/PostGIS, real vision models, and the farmer/mobile experience are sequenced in [Docs/ROADMAP.md](Docs/ROADMAP.md).

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

To run the API with the local Qdrant service:

```powershell
docker compose up --build
```

### Extension-officer dashboard

Run the API first, then start the separate local dashboard in another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The dashboard defaults to the local API at
`http://127.0.0.1:8000`; change `VITE_API_BASE_URL` in `frontend/.env` only when
using a different endpoint. It deliberately labels review-pending advice as a
draft and records an append-only demo decision history for each case.

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

The seed records are synthetic. Do not add real farmer data, credentials, Aadhaar numbers, or production exports to this repository. The service must remain behind consent, deterministic verification, and Human-in-the-Loop gates before it can be used for consequential advice.

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

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Contributions that affect recommendations, safety rules, data access, or consent flows require domain and security review.
