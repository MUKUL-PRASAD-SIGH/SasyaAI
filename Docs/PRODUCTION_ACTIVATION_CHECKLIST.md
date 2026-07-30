# Production Activation Checklist

This checklist distinguishes what is implemented in the repository from the
actions that need a named human owner, legal approval, credentials, or live
infrastructure. Do not activate real farmer data until every applicable item
is evidenced and signed off.

## Implemented local foundations

- API-key authentication/RBAC adapter, farmer-assignment filtering, and
  in-process rate limiting.
- Typed synthetic consent preflight and provenance contracts.
- Data-minimised local audit log, runtime retention, and deletion-request
  receipts that mark external cleanup as pending.
- Version-labelled deterministic safety path, non-overridable failed checks,
  backend/component/browser regression tests, and CI browser-test coverage.

These are foundations only. Local API keys, local JSON logs, and in-process
rate limits are not sufficient production controls.

## Human-owned activation gates

| Gate | Human owner | Required action | Evidence before activation |
|---|---|---|---|
| Identity and access | Security lead + platform engineer | Replace API-key adapter with approved OIDC/JWT gateway, define role-to-scope mappings and extension-officer assignment source, store secrets in an approved manager | Threat model, gateway config review, access tests, secret-rotation record |
| Rate limiting and edge protection | Platform/SRE | Enforce distributed limits, WAF/bot controls, trusted proxy handling, and alert thresholds at the gateway | Load test, abuse test, dashboard/alert runbook |
| Consent | Privacy lead + AgriStack integration owner | Obtain official sandbox/production schemas and credentials, verify signed receipts, implement revocation propagation and cleanup acknowledgements | Contract tests, revocation drill, data-processing approval |
| Data adapters | Data owner + agricultural domain lead | Approve authoritative sources, freshness limits, fallbacks, licences, and field mappings for weather, schemes, pest protocols, land and market data | Source register, sample evidence, freshness/error tests |
| Safety rules | Agricultural domain lead + safety reviewer | Approve each rule-set version, dose/unit interpretation, localisation, escalation criteria, and rollback procedure | Signed rule release, regression/evaluation report, change log |
| Evaluation | ML/domain lead | Assemble consented evaluation data, define target metrics and error budgets, and run regional/language validation | Dataset governance record, model/rule evaluation report, acceptance decision |
| Durable data and backup | Data platform owner | Replace local JSON state with encrypted, access-controlled stores; define backup retention, restore testing, DSAR propagation, and data residency | Schema/migration review, backup-restore drill, retention policy |
| Observability and incidents | SRE + security lead | Add production metrics, central audit export, SIEM integration, alerts, on-call ownership, and incident response exercises | Dashboard links, alert tests, incident tabletop record |
| Security assurance | Security lead | Run dependency/container scanning, SAST, DAST, penetration testing, and remediation tracking | Scan reports, pen-test closure, risk acceptance where needed |
| Frontend and release | Frontend lead + QA | Connect the dashboard to approved browser authentication, run cross-browser/accessibility checks, and protect release environments | E2E results, accessibility report, release checklist |

## Configuration rules

- `APP_ENVIRONMENT` must not be `development` outside a local demo.
- Set `AUTH_REQUIRED=true` outside local development. `AUTH_PRINCIPALS_JSON`
  is an environment-only transitional adapter, never a tracked or browser-side
  value.
- Keep `LYZR_*`, `QDRANT_*`, external provider credentials, and production
  connection strings in a secret manager. Empty placeholders do not enable an
  integration.
- Set an approved `SAFETY_RULE_SET_VERSION` for every release and retain the
  corresponding approval/evaluation evidence.
- Treat every deletion receipt with `pending_external_cleanup` as open until
  owners evidence purge/retention handling across all live stores and backups.

## Explicit non-goals of the local demonstrator

- It does not authenticate real users or issue JWTs.
- It does not make live provider calls or verify a real consent receipt.
- It does not contain real farmer data, production secrets, authoritative
  agronomy evidence, or a durable production datastore.
- It does not replace legal, privacy, security, agricultural-domain, or
  operational sign-off.
