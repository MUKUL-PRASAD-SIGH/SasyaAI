# SasyaAI Testing Guide

The current suite validates the local, synthetic-data demonstrator. It does
not certify agricultural advice, live integrations, or production readiness.

## Automated checks

From the repository root, activate a clean Python 3.10+ virtual environment
and run:

```powershell
python -m pytest -q
python -m ruff check backend tests
```

The API tests cover delivered advice, a Karnataka water-budget regression,
low-confidence diagnosis routing, unsafe-dose blocking, consent denial,
atomic HITL decisions, protected-mode authentication/RBAC, farmer assignments,
rate limits, audit metadata, local retention/deletion, and controlled errors.

Build the extension-officer dashboard separately:

```powershell
Set-Location frontend
npm ci
npm test
npm run build
```

The component suite covers case-bound review context, case-switch form resets,
and edit validation. The browser suite starts the local FastAPI and Vite
servers, then verifies that a failed deterministic safety case offers only
rejection:

```powershell
npx playwright install chromium
npm run test:e2e
```

## Manual demo checks

1. Start the API and dashboard using the commands in the README.
2. Run the **Crop plan** scenario and confirm the result is delivered only
   after the water, financial, weather, scheme, and dose checks are shown.
3. Run **Leaf spots** and confirm the response is labelled *Awaiting human
   review*, with a review case containing the draft, evidence, checks, and
   trace.
4. Use **Edit and approve** only for the low-confidence **Leaf spots** case,
   then confirm a second decision is rejected by the API.
5. Run **Aphid dose · blocked** and confirm a 3 ml/L dose is never delivered.
   Its review form must offer only **Reject draft**.

## Test data and boundaries

- Only checked-in files under `data/seed/` may be used for the demo.
- Test/runtime JSON is written below ignored `var/`; do not add it to source
  control.
- Use a clean virtual environment. Global Python environments can contain
  unrelated packages with conflicting binary dependencies.
- Any change to safety thresholds, knowledge records, or verifier logic needs
  a new regression test and agricultural-domain review.
- Browser E2E tests require the Playwright browser download; CI installs it
  before running `npm run test:e2e`.
