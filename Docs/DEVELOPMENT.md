# SasyaAI Development Guide

## Local setup

Use Python 3.10+ for the FastAPI demonstrator and Node.js 20+ for the officer
dashboard.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
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
- `data/seed/` holds reviewed synthetic farmers and knowledge facts.
- `backend/app/services/memory.py` is the only local persistence boundary for
  advisory episodes and review cases.
- `frontend/` is a Vite/React review interface. It does not decide safety or
  bypass the API verifier.
- `var/`, `.env`, model artifacts, and real farmer data must remain untracked.

## Development rules

1. Do not add real farmer records, credentials, Aadhaar data, or sandbox
   tokens.
2. Keep a verifier check tied to values in the actual recommendation; never
   make a safety check a hard-coded success message.
3. Pending or failed advice must remain review-pending in every client view.
4. Only the Memory boundary can mutate local runtime data.
5. Run the commands in [TESTING.md](TESTING.md) before handing over a change.

## Configuration

`.env.example` documents optional future-facing Lyzr and Qdrant values. The
current local workflow does not use credentials and operates from seed JSON.
`frontend/.env.example` contains the independent dashboard API base URL.
