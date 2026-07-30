# SasyaAI deployment guide

## Local four-service stack

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The stack contains:

- Nginx operations UI on `http://127.0.0.1:5173`;
- FastAPI on `http://127.0.0.1:8000`;
- PostgreSQL on port `5432`; and
- Qdrant on ports `6333` and `6334`.

The UI uses same-origin `/api/*` and `/health` proxying. Both UI and API images
have health checks. PostgreSQL and Qdrant use named volumes; demo JSON state
uses `./var`, which is ignored by Git.

Compose uses `.env` by default. Configuration-only validation can use the
checked-in example without creating a local secret file:

```powershell
$env:ENV_FILE = ".env.example"
docker compose config --quiet
```

## Runtime choice

`RUNTIME_MODE=demo` is the default and never touches PostgreSQL, Qdrant, Gemini,
or live providers for advisory work. It is an evaluation runtime over
synthetic data.

`RUNTIME_MODE=production` refuses startup unless live credentials,
authentication, durable stores, and OTLP tracing are configured. It does not
fall back to demo records. Follow [Production Runtime](PRODUCTION_RUNTIME.md)
and the [Production Activation Checklist](PRODUCTION_ACTIVATION_CHECKLIST.md).

## Images

The API image preloads the pinned FastEmbed multilingual ONNX model at build
time. This avoids a first-request model download and does not install CUDA.
Override `EMBEDDING_MODEL` only by building a new image and rebuilding empty
Qdrant collections with the matching vector dimension.

The dashboard is built with Node 22 and served by Nginx with a restrictive
Content Security Policy, static-asset caching, and a dynamically resolved API
upstream.

## Protected access

Production requires `AUTH_REQUIRED=true`. The transitional credential adapter
accepts role-scoped `X-API-Key` values from a secret source. The internal UI
keeps an entered key in memory only and clears it on reload. Do not compile a
credential into `VITE_*` variables. Put OIDC and a backend-for-frontend gateway
in front of any public deployment.

## Release checks

```powershell
python -m ruff check backend tests scripts
python -m pytest -q

Set-Location frontend
npm ci
npm audit
npm run build
npm test
npm run test:e2e
```

Also validate Compose, build both images, and run container health smoke tests.
CI executes lint, backend tests, frontend component/build checks, and Chromium
E2E journeys.

## Non-local deployment

The checked-in Compose stack is a reproducible integration environment, not a
complete public-cloud runbook. Before a pilot, provide managed encrypted stores,
secret management, OIDC, distributed rate limits, WAF controls, India-resident
data placement, backups and restore drills, central audit/SIEM export, provider
contract tests, load testing, accessibility testing, and domain/legal approval.
