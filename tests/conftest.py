"""Keep automated tests independent from a developer's local .env mode."""

import os

# Pydantic Settings reads .env at import time. These collection defaults keep
# a local production configuration from preventing demo-contract tests from
# importing the FastAPI module; production-boundary tests pass explicit
# Settings instances where they need to exercise startup gates.
os.environ.setdefault("APP_ENVIRONMENT", "development")
os.environ.setdefault("RUNTIME_MODE", "demo")
os.environ.setdefault("AUTH_REQUIRED", "false")
os.environ.setdefault("AUTH_PRINCIPALS_JSON", "")
