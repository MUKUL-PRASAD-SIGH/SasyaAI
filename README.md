# SasyaAI

Safety-gated agricultural advisory for Indian farmers — digital twin, grounded retrieval, specialised agents, deterministic verification, and human review.

| Mode | What it is |
|---|---|
| `RUNTIME_MODE=demo` | Local, credentialed workflow over synthetic seed data. Not a live advisory service. |
| `RUNTIME_MODE=production` + `PRODUCTION_DATA_MODE=synthetic` | Real auth, PostgreSQL, Qdrant, Gemini — labelled synthetic corpus only. |
| `RUNTIME_MODE=production` + `PRODUCTION_DATA_MODE=live` | AgriStack-ready path after gateway approval. |

Default `.env.example` uses **demo** mode with auth on so reviewers can exercise RBAC immediately.

---

## What's new (hackathon)

| Feature | Notes |
|---|---|
| Role-based Sign-in | Farmer / Extension Officer / System Admin gate on first screen |
| Email OTP + API key | Either method; OTP returns `otp_demo_code` in development |
| Farmer onboarding | **Register new farmer** → session token; appears in officer/admin farmer lists by region |
| RBAC scoping | `allowed_farmer_ids` / `allowed_regions`; officers see assigned farms only |
| Rate limits + injection guards | Per-role sliding windows; prompt override patterns refused |
| Image upload | Preprocess + YOLO11 ONNX plant-disease detect when `best.onnx` present; else pixel CV. See [Docs/VISION_PIPELINE.md](Docs/VISION_PIPELINE.md) |
| Agent thinking UI | Live workflow / thinking timeline after a run |
| Learning from feedback | Farmer feedback feeds memory / future advice |
| **3 roles only** | No FPO / Policy Analyst in this build |

---

## Quick start

**Prereqs:** Docker Desktop (Compose route) · Python 3.10+ · Node.js 22+ (local frontend only)

### 1. Clone & env

```powershell
cd SasyaAI
Copy-Item .env.example .env
Copy-Item REVIEWER_CREDENTIALS.example.md REVIEWER_CREDENTIALS.md
```

`REVIEWER_CREDENTIALS.md` and `.env` are gitignored — never commit them.

Optional: set `GEMINI_API_KEY` in `.env` for real LLM drafts in production mode.

### 2A. Docker Compose (recommended for reviewers)

```powershell
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://127.0.0.1:5173 |
| API + docs | http://127.0.0.1:8000 · http://127.0.0.1:8000/docs |

Starts dashboard, API, PostgreSQL, and Qdrant.

**Frontend changes in Docker:** the dashboard image is baked at build time. After editing `frontend/`, rebuild:

```powershell
docker compose up -d --build dashboard
```

Then hard-refresh the browser.

After backend onboarding or API route changes, rebuild the **api** service as well — rebuilding **dashboard** alone leaves stale routes in the running API container:

```powershell
docker compose up -d --build api dashboard
```

### 2B. Local API + Vite (dev)

**Terminal 1 — API**

```powershell
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

Local Vite proxies to `VITE_API_BASE_URL=http://127.0.0.1:8000` (see `frontend/.env.example`).

### Smoke checks

```powershell
python -m pytest -q
python -m ruff check backend tests scripts
# frontend (from frontend/)
npm test
```

### Example advisory call

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

### Optional: plant-disease ONNX vision

Large weights stay **out of git**. If you have `PlantDiseaseDetection.pt`:

```powershell
pip install ultralytics onnx onnxruntime pyyaml
python scripts/setup_vision.py --pt models/yolov8_npss/PlantDiseaseDetection.pt
```

This creates `models/yolov8_npss/best.onnx` + `labels.yaml`. With `VISION_BACKEND=auto` the API uses YOLO detect when `best.onnx` exists; otherwise pixel CV. **Do not push** `.pt` / `.onnx` to GitHub. Details: [Docs/VISION_PIPELINE.md](Docs/VISION_PIPELINE.md).

---

## Hands-on: three roles

Open **http://127.0.0.1:5173** → pick a role → **API key** or **Email OTP**.

| Role | API key | Email (OTP) |
|---|---|---|
| Farmer | `farmer-demo-key-0123456789abcdef` | `asha.patil@demo.sasyaai.local` |
| Officer (West) | `officer-west-demo-key-0123456789ab` | `officer.west@demo.sasyaai.local` |
| Officer (South) | `officer-south-demo-key-0123456789a` | `officer.south@demo.sasyaai.local` |
| System Admin | `admin-demo-key-0123456789abcdef0` | `admin@demo.sasyaai.local` |

OTP: choose Email OTP → submit email → use `otp_demo_code` from the API response → continue.

| Role | Walkthrough |
|---|---|
| **Farmer** | Sign in → ask an advisory question → **Images** tab to upload → attach image ID on query → watch **Agents / thinking** timeline → optional **Register new farmer** on login (new profile lands in regional officer/admin dropdowns). |
| **Extension Officer** | Sign in (West or South) → farmer list is region-scoped only → open **HITL queue** → approve / reject pending cases. |
| **System Admin** | Sign in → all farmers visible → runtime/health, audit, sync/config actions, full HITL view. |

Full cheat-sheet: `REVIEWER_CREDENTIALS.md` (after copy). Same keys live in `.env` as `AUTH_PRINCIPALS_JSON`.

---

## Security & RBAC

Thin local auth adapter for demos — not a production IdP.

| Topic | Detail |
|---|---|
| `AUTH_REQUIRED` + API keys | Principals: `subject`, `roles`, optional `allowed_farmer_ids` / `allowed_regions` |
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
2. Tools + state-filtered Qdrant memory (farmer-scoped episodes)  
3. Gemini drafts with evidence IDs → reflection check  
4. Deterministic verifier (weather, dose, confidence, synthetic boundaries)  
5. Deliver or durable HITL case in PostgreSQL  

Gemini is never the source of truth. Qdrant = semantic memory; PostgreSQL = profiles, consent, episodes, HITL, audit. Production config: [Production Runtime](Docs/PRODUCTION_RUNTIME.md).

---

## Repository layout

```text
backend/     FastAPI, contracts, workflow, adapters
data/seed/   Synthetic farmers + knowledge
Docs/        Architecture, API, security, deployment
frontend/    Vite/React operations dashboard
scripts/     Evaluation-corpus tooling
tests/       API + workflow regression
```

---

## Safety

Seed data is **synthetic**. Do not commit real farmer PII, credentials, or Aadhaar. Failed hard safety checks cannot be overridden via HITL approve — reject and re-ask with safe parameters only.

---

## Docs

| Doc | Link |
|---|---|
| Master plan | [MASTER_PLAN](Docs/MASTER_PLAN.md) |
| Architecture | [ARCHITECTURE](Docs/ARCHITECTURE.md) |
| API | [API](Docs/API.md) |
| Security | [SECURITY](Docs/SECURITY.md) |
| Production runtime | [PRODUCTION_RUNTIME](Docs/PRODUCTION_RUNTIME.md) |
| Deployment | [DEPLOYMENT](Docs/DEPLOYMENT.md) |
| Development | [DEVELOPMENT](Docs/DEVELOPMENT.md) |
| Testing | [TESTING](Docs/TESTING.md) |
| Agent ops | [AGENT_OPERATIONS](Docs/AGENT_OPERATIONS.md) |
| Dataset card | [DATASET_CARD](data/seed/DATASET_CARD.md) |
| Contributing | [CONTRIBUTING](CONTRIBUTING.md) |
