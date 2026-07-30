"""Local API-key authentication, RBAC, and rate-limit primitives.

This module is intentionally an adapter boundary, not a replacement for a
production identity provider or API gateway.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from app.models.security import ApiKeyCredential, Principal, Role

if TYPE_CHECKING:
    from fastapi import Request


class AuthenticationError(RuntimeError):
    """Raised when a protected request has no valid credential."""


class AuthorizationError(RuntimeError):
    """Raised when a valid principal lacks role or farmer assignment access."""


class RateLimitExceededError(RuntimeError):
    """Raised when an in-process caller bucket exceeds its configured window."""


class SecurityConfigurationError(RuntimeError):
    """Raised when protected mode is enabled without valid credential records."""


@dataclass(frozen=True)
class RateLimitPolicy:
    requests: int
    window_seconds: int


class ApiKeyAuthorizer:
    """Verifies environment-provided API keys and enforces roles/assignments."""

    def __init__(self, *, auth_required: bool, credential_json: str, environment: str) -> None:
        self.auth_required = auth_required
        self.environment = environment.lower()
        self._credentials = self._parse_credentials(credential_json)
        if self.auth_required and not self._credentials:
            raise SecurityConfigurationError(
                "AUTH_REQUIRED needs at least one AUTH_PRINCIPALS_JSON credential."
            )
        if self.environment != "development" and not self.auth_required:
            raise SecurityConfigurationError(
                "AUTH_REQUIRED must be enabled outside the development environment."
            )

    @staticmethod
    def _parse_credentials(credential_json: str) -> list[ApiKeyCredential]:
        if not credential_json.strip():
            return []
        try:
            raw_credentials = json.loads(credential_json)
            return TypeAdapter(list[ApiKeyCredential]).validate_python(raw_credentials)
        except (json.JSONDecodeError, ValidationError) as error:
            raise SecurityConfigurationError("AUTH_PRINCIPALS_JSON is not a valid credential list.") from error

    def authenticate(self, request: Request) -> Principal:
        if not self.auth_required:
            return Principal(
                subject="local-development-bypass",
                roles=frozenset(Role),
                authentication_method="development_bypass",
            )

        supplied_key = request.headers.get("X-API-Key", "")
        if not supplied_key:
            raise AuthenticationError("A valid X-API-Key is required.")

        for credential in self._credentials:
            if secrets.compare_digest(supplied_key, credential.api_key):
                return Principal(
                    subject=credential.subject,
                    roles=credential.roles,
                    allowed_farmer_ids=credential.allowed_farmer_ids,
                    authentication_method="api_key",
                )
        raise AuthenticationError("The supplied API key is not valid.")

    @staticmethod
    def require_roles(principal: Principal, allowed_roles: frozenset[Role]) -> None:
        if not principal.roles.intersection(allowed_roles):
            raise AuthorizationError("This principal does not have the required role.")

    @staticmethod
    def require_farmer_assignment(principal: Principal, farmer_id: str) -> None:
        if principal.authentication_method == "development_bypass" or Role.SYSTEM_ADMIN in principal.roles:
            return
        if principal.allowed_farmer_ids is None or farmer_id not in principal.allowed_farmer_ids:
            raise AuthorizationError("This principal is not assigned to the requested farmer.")


class SlidingWindowRateLimiter:
    """Thread-safe, bounded in-memory rate limiting for the local API process."""

    def __init__(self, policy: RateLimitPolicy) -> None:
        self.policy = policy
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def check(self, request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        key_fingerprint = hashlib.sha256(
            request.headers.get("X-API-Key", "anonymous").encode("utf-8")
        ).hexdigest()[:16]
        key = f"{client_host}:{key_fingerprint}"
        now = monotonic()
        cutoff = now - self.policy.window_seconds

        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.policy.requests:
                raise RateLimitExceededError("Rate limit exceeded; retry after the configured window.")
            bucket.append(now)
