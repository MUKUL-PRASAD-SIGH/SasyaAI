# SasyaAI Development Guide

## Current implementation footprint

The working implementation in this workspace already includes:

- a FastAPI entrypoint in [backend/app/main.py](../backend/app/main.py) for auth, onboarding, advisory queries, image upload, feedback, HITL review, audit, and runtime deletion flows
- a Vite/React dashboard in [frontend/src/App.tsx](../frontend/src/App.tsx) with farmer, officer, and admin views
- deterministic advisory and safety logic in [backend/app/services/advisory.py](../backend/app/services/advisory.py) and [backend/app/services/security.py](../backend/app/services/security.py)

The local demo remains the best place to validate behaviour before enabling production-only integrations.

## Local setup

Use Python 3.10+ for FastAPI and Node.js 22+ for the officer
dashboard.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

The API serves `http://127.0.0.1:8000` and the dashboard serves
`http://127.0.0.1:5173` by default.

## Repository boundaries

- `backend/app/` owns API contracts, workflow, and local adapters.
- `data/seed/` holds generated synthetic evaluation profiles and references.
- `backend/app/services/memory.py` is the only local persistence boundary for
  advisory episodes and review cases.
- `frontend/` is a Vite/React review interface. It does not decide safety or
  bypass the API verifier.
- `var/`, `.env`, model artifacts, and real farmer data must remain untracked.
- Crop image upload runs a **real preprocess + pixel CV pipeline** (optional ONNX
  when weights exist). See [VISION_PIPELINE.md](VISION_PIPELINE.md). Filename
  heuristics are gone; trained YOLO/NPSS weights remain optional under `/models/`.

## Development rules

1. Do not add real farmer records, credentials, Aadhaar data, or sandbox
   tokens.
2. Keep a verifier check tied to values in the actual recommendation; never
   make a safety check a hard-coded success message.
3. Pending or failed advice must remain review-pending in every client view.
4. Only the Memory boundary can mutate local runtime data.
5. Run the commands in [TESTING.md](TESTING.md) before handing over a change.

## Configuration

`.env.example` documents both production provider settings and the optional
future Lyzr boundary. The local demo does not use credentials and operates from
seed JSON; production uses Gemini, PostgreSQL, Qdrant/FastEmbed, and live tools.
`frontend/.env.example` contains the independent dashboard API base URL.
