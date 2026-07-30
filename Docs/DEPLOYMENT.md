# SasyaAI Demonstrator Deployment Guide

This guide covers the local synthetic-data demonstrator only. It is not a
production deployment runbook.

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API is available on port `8000`. The current FastAPI workflow uses seed
JSON rather than Qdrant, so the default Compose route is self-contained and
does not start a retrieval container.

To include the optional local Qdrant container (ports `6333` and `6334`) for
future retrieval experiments, run:

```powershell
docker compose --profile retrieval up --build
```

Qdrant is present for the next retrieval integration phase and is not evidence
of live semantic search.

Compose mounts `./var` into the API container so local advisory episodes and
HITL decisions survive an API-container restart. It contains only synthetic
demo state and is ignored by Git.

## Protected-mode foundation

The default `.env.example` keeps the local synthetic demo open. Any non-local
environment must set `AUTH_REQUIRED=true`, provide `AUTH_PRINCIPALS_JSON` from
a secret manager, configure an approved `SAFETY_RULE_SET_VERSION`, and set an
explicit retention period. The current API-key mechanism is a transitional
adapter; do not put its value in a browser environment file. Replace it with
the approved OIDC/JWT gateway and distributed rate limiting before production.

Follow [PRODUCTION_ACTIVATION_CHECKLIST.md](PRODUCTION_ACTIVATION_CHECKLIST.md)
for the live-consent, provider, database, audit-export, backup, monitoring,
and security gates that are not activated by this repository.

## Dashboard

The officer dashboard is intentionally run as a separate local Vite process:

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm ci
npm run build
npm run preview
```

For development, use `npm run dev`. Set `VITE_API_BASE_URL` only when the API
is served from a different address. Configure the API `CORS_ORIGINS` to include
the dashboard origin.

## Before any non-local deployment

Do not deploy this demo with real farmer data. Complete the consent, identity,
secret management, source-freshness, audit durability, sandbox, security, and
domain-review gates described in [ROADMAP.md](ROADMAP.md) and
[SECURITY.md](SECURITY.md) first.
