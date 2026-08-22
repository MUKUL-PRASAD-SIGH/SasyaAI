# SasyaAI

Safety-gated agricultural advisory for Indian farmers — the current branch ships a working demo stack with a FastAPI backend, a Vite dashboard, role-based auth, farmer onboarding, crop-image upload, advisory workflow, HITL review, and runtime/audit endpoints. The implementation is demo-first and synthetic, but the consent gates, verification checks, and reviewer flows are wired end to end.

| Mode | What it is |
|---|---|
| `RUNTIME_MODE=demo` | Local, credentialed workflow over synthetic seed data. Fastest path for reviewers. |
| `RUNTIME_MODE=production` + `PRODUCTION_DATA_MODE=synthetic` | Real auth, PostgreSQL, Qdrant, Gemini — labelled synthetic corpus only. |
| `RUNTIME_MODE=production` + `PRODUCTION_DATA_MODE=live` | AgriStack-ready path after gateway approval. |

Default [`.env.example`](.env.example) uses **demo** mode with auth on so reviewers can exercise RBAC immediately.

---

## What's implemented now

| Feature | Current state |
|---|---|
| **Role-based sign-in** | Farmer, Extension Officer, and System Admin roles are available from the dashboard and API auth flow |
| **Farmer passwordless login** | Email OTP, **Continue with Google (demo)**, and **Register new farmer** are wired in the current build |
| **Farmer onboarding** | New farmers can be registered, issued a scoped session, and assigned to the regional officer desk |
| **RBAC desk scoping** | Farmers see their own farm, officers see region-assigned farms, and admins view the wider runtime |
| **Inline crop image upload** | Upload works from the advisory flow and the Images tab without manual image-ID entry |
| **Vision pipeline** | The API supports preprocess + pixel CV, with optional ONNX vision when weights are present ([Docs/VISION_PIPELINE.md](Docs/VISION_PIPELINE.md)) |
| **Agent thinking UI** | The workflow timeline and agent-run cards are displayed after a query run |
| **HITL + feedback** | Officer review queue, decision handling, and feedback capture are implemented in the demo runtime |
| **Safety controls** | Per-role rate limits, prompt-injection sanitisation, consent preflight, and deterministic verification are active |
| **Roles in this build** | The shipped demo currently uses the three roles above; no FPO or Policy Analyst role is included |

---

## How to use locally (for others)

### Prerequisites

- **Docker Desktop** (recommended), or
- **Python 3.10+** and **Node.js 22+** for a local Vite + uvicorn setup
- Windows PowerShell examples below; Linux/macOS: use `cp` instead of `Copy-Item`, and `source .venv/bin/activate`

### Option A — Docker Compose (recommended)

```powershell
git clone <this-repo-url> SasyaAI
cd SasyaAI
Copy-Item .env.example .env
Copy-Item REVIEWER_CREDENTIALS.example.md REVIEWER_CREDENTIALS.md
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://127.0.0.1:5174 |
| API + OpenAPI | http://127.0.0.1:8001 · http://127.0.0.1:8001/docs |

Starts dashboard, API, PostgreSQL, and Qdrant. Compose mounts `./models` into the API so optional ONNX weights are picked up automatically.

**After code changes**

```powershell
# Frontend only
docker compose up -d --build dashboard

# Backend / API routes / vision
docker compose up -d --build api

# Both
docker compose up -d --build api dashboard
```

Hard-refresh the browser after a dashboard rebuild.

### Option B — Local API + Vite (dev)

**Terminal 1 — API**

```powershell
cd SasyaAI
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --app-dir backend --reload
```

**Terminal 2 — dashboard**

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm install
npm run dev
```

| App | URL |
|---|---|
| Vite dashboard | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 |

Vite proxies `/api` and `/health` to port 8000 (see [`frontend/vite.config.ts`](frontend/vite.config.ts)). Keep `RUNTIME_MODE=demo` in `.env` unless you have Postgres + Qdrant running.

### First login walkthrough

1. Open http://127.0.0.1:5173
2. Pick a role:
   - **Farmer** — Email OTP, Continue with Google (demo), or **Register new farmer**
   - **Officer / Admin** — Email OTP or Advanced API key
3. Demo credentials (also in `.env` as `AUTH_PRINCIPALS_JSON`):

| Role | API key | Email (OTP) |
|---|---|---|
| Farmer | `farmer-demo-key-0123456789abcdef` | `asha.patil@demo.sasyaai.local` |
| Officer (West) | `officer-west-demo-key-0123456789ab` | `officer.west@demo.sasyaai.local` |
| Officer (South) | `officer-south-demo-key-0123456789a` | `officer.south@demo.sasyaai.local` |
| System Admin | `admin-demo-key-0123456789abcdef0` | `admin@demo.sasyaai.local` |

4. OTP: Request OTP → copy `otp_demo_code` from the UI / API response → Sign in  
5. New farmers: **Register new farmer** first; then that email can OTP / Google-demo login

Copy [`REVIEWER_CREDENTIALS.example.md`](REVIEWER_CREDENTIALS.example.md) → `REVIEWER_CREDENTIALS.md` for a local cheat-sheet (gitignored).

### Try the product

| Role | What to do |
|---|---|
| **Farmer** | Register or sign in → **Ask advisory** → type a question → optional **Crop image** upload → **Run advisory workflow** → watch **Agents** |
| **Extension Officer** | Sign in (West/South) → **Assigned farmers** (region-scoped) → **HITL queue** → approve / reject |
| **System Admin** | Sign in → all farmers, runtime/health, audit, full HITL |

### Optional — disease + pest ONNX vision

Large weights stay **out of git** (`.pt` / `.onnx` are gitignored). Without weights the API still runs **pixel CV**.

```powershell
# 1) Place Ultralytics weights locally, e.g.:
#    models/yolov8_npss/PlantDiseaseDetection.pt
#    models/pest/best.pt

# 2) Export ONNX + labels
pip install ultralytics onnx onnxruntime pyyaml
python scripts/setup_vision.py --pt models/yolov8_npss/PlantDiseaseDetection.pt
python scripts/setup_vision.py --model pest --pt models/pest/best.pt

# 3) Ensure .env has:
#    VISION_BACKEND=auto
#    VISION_HITL_THRESHOLD=0.70

# 4) Restart API (Docker remounts ./models automatically)
docker compose up -d --build api
```

Creates each specialist's `best.onnx` + `labels.yaml`. In `auto`, both installed specialists run; if neither can run, pixel CV remains the fallback. **Do not push** weight files to GitHub. Details: [Docs/VISION_PIPELINE.md](Docs/VISION_PIPELINE.md).

### Smoke checks

```powershell
python -m pytest -q
python -m pytest tests/vision -q
python -m ruff check backend tests scripts
# from frontend/
npm test
```

### Example advisory API call

```powershell
$body = @{
  farmer_id = "AGR_MH_001234"
  query = "Should I switch from cotton to soybean?"
  language = "mr"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/query `
  -Headers @{"X-API-Key" = "farmer-demo-key-0123456789abcdef"} `
  -ContentType "application/json" -Body $body
```

Registered farmers can use the session token from signup as `Authorization: Bearer <token>` or `X-API-Key: <token>` instead of the demo farmer key.

### Common pitfalls

| Symptom | Fix |
|---|---|
| `405` on `/api/v1/farmers/register` | Rebuild **api**, not only dashboard |
| Image upload `500` / multipart error | Ensure `python-multipart` is installed (in `requirements.txt`); rebuild api |
| Vision always pixel, never ONNX | Confirm at least one of `models/yolov8_npss/best.onnx` or `models/pest/best.onnx` exists and `VISION_BACKEND=auto` |
| Empty farmer list after register | Sign out/in; farmer desk is scoped to `allowed_farmer_ids` |
| Production mode won't start | Fill required `.env` keys or switch to `RUNTIME_MODE=demo` |

Never commit `.env`, `REVIEWER_CREDENTIALS.md`, `var/`, or model weight files.

---

## Security & RBAC

Thin local auth adapter for demos — not a production IdP.

| Topic | Detail |
|---|---|
| `AUTH_REQUIRED` + session / API keys | Principals: `subject`, `roles`, optional `allowed_farmer_ids` / `allowed_regions` |
| Demo corpus | ~18 synthetic farmers — contract/UI review only |
| Production path | Replace keys with JWT/OIDC; Google OAuth stubbed (`GOOGLE_OAUTH_ENABLED`) |

| Role | Can do | Cannot do |
|---|---|---|
| `farmer` | Own profile, advisory, image upload, feedback, own history | Other farmers, HITL, audit/config |
| `extension_officer` | Assigned/region farmers, HITL review, metrics | Unassigned farmers, system audit/config |
| `system_admin` | All farmers, runtime/sync/audit/config, deletion | — |

Also in-repo: prompt-injection sanitisation, SQLAlchemy bound params, per-role rate limits, data-minimised audit + immutable HITL attribution. See [Security](Docs/SECURITY.md).

---

## How an answer is produced

1. Intent router → crop / pest / scheme specialist  
2. Optional crop-image vision (ONNX or pixel) attached as evidence context  
3. Tools + state-filtered Qdrant memory (farmer-scoped episodes)  
4. Gemini drafts with evidence IDs → reflection check  
5. Deterministic verifier (weather, dose, confidence, synthetic boundaries)  
6. Deliver or durable HITL case  

Gemini is never the source of truth. Qdrant = semantic memory; PostgreSQL = profiles, consent, episodes, HITL, audit (production). Config: [Production Runtime](Docs/PRODUCTION_RUNTIME.md).

---

## Repository layout

```text
backend/          FastAPI, contracts, workflow, vision, adapters
data/seed/        Synthetic farmers + knowledge
Docs/             Architecture, API, security, vision, deployment
frontend/         Vite/React role-scoped dashboard
models/yolov8_npss/  labels.yaml + README (weights gitignored)
scripts/          setup_vision.py, corpus tooling
tests/            API + vision regression
```

---

## Safety

Seed data is **synthetic**. Do not commit real farmer PII, credentials, or Aadhaar. Failed hard safety checks cannot be overridden via HITL approve — reject and re-ask with safe parameters only.

---

## Docs

| Doc | Link |
|---|---|
| Vision pipeline | [VISION_PIPELINE](Docs/VISION_PIPELINE.md) |
| Master plan | [MASTER_PLAN](Docs/MASTER_PLAN.md) |
| Architecture | [ARCHITECTURE](Docs/ARCHITECTURE.md) |
| API | [API](Docs/API.md) |
| Security | [SECURITY](Docs/SECURITY.md) |
| Production runtime | [PRODUCTION_RUNTIME](Docs/PRODUCTION_RUNTIME.md) |
| Deployment | [DEPLOYMENT](Docs/DEPLOYMENT.md) |
| Development | [DEVELOPMENT](Docs/DEVELOPMENT.md) |
| Testing | [TESTING](Docs/TESTING.md) |
| Demo recording guide | [DEMO_RECORDING_GUIDE](Docs/DEMO_RECORDING_GUIDE.md) |
| Agent ops | [AGENT_OPERATIONS](Docs/AGENT_OPERATIONS.md) |
| Dataset card | [DATASET_CARD](data/seed/DATASET_CARD.md) |
| Contributing | [CONTRIBUTING](CONTRIBUTING.md) |
