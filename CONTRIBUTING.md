# Contributing to SasyaAI

SasyaAI is a safety-gated agricultural-advisory demonstrator. Changes are
welcome, but safety and synthetic-data boundaries come first.

## Before opening a change

1. Keep the change focused and document any product or safety assumption.
2. Never commit real farmer data, Aadhaar data, credentials, API tokens,
   runtime `var/` files, or model artifacts.
3. Add or update a regression test for API behavior, safety checks, or HITL
   transitions.
4. Run the checks in [Docs/TESTING.md](Docs/TESTING.md).

## Required review

Changes to pesticide limits, crop/scheme knowledge, confidence thresholds,
consent behavior, data access, or deployment controls require agricultural
domain and security review before merge.

## Style

- Use typed contracts for API and workflow boundaries.
- Keep persistence behind the Memory service.
- Preserve the distinction between reflection, deterministic verification, and
  human review.
- Do not render a pending recommendation as farmer-ready advice.
