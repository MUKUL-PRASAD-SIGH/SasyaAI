# SasyaAI Demonstrator Deployment Guide

This guide covers the local synthetic-data demonstrator only. It is not a
production deployment runbook.

## Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API is available on port `8000`; the optional local Qdrant container is
available on ports `6333` and `6334`. The current FastAPI workflow uses seed
JSON rather than Qdrant, so Qdrant is present for the next retrieval
integration phase and is not evidence of live semantic search.

Compose mounts `./var` into the API container so local advisory episodes and
HITL decisions survive an API-container restart. It contains only synthetic
demo state and is ignored by Git.

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
