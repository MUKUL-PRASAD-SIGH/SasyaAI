"""Local API-key authentication, RBAC, and rate-limit primitives.

This module is intentionally an adapter boundary, not a replacement for a
production identity provider or API gateway.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from time import time
from typing import TYPE_CHECKING, Any, Literal

from pydantic import TypeAdapter, ValidationError

from app.models.security import ApiKeyCredential, Principal, Role

if TYPE_CHECKING:
    from fastapi import Request

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompts?)", re.I),
    re.compile(r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)", re.I),
    re.compile(r"system\s*prompt\s*:", re.I),
    re.compile(r"<\s*/?\s*system\s*>", re.I),
    re.compile(r"override\s+(safety|policy|rules?)", re.I),
    re.compile(r"reveal\s+(your\s+)?(system|hidden)\s+(prompt|instructions?)", re.I),
)


class AuthenticationError(RuntimeError):
    """Raised when a protected request has no valid credential."""


class AuthorizationError(RuntimeError):
    """Raised when a valid principal lacks role or farmer assignment access."""


class RateLimitExceededError(RuntimeError):
    """Raised when an in-process caller bucket exceeds its configured window."""


class SecurityConfigurationError(RuntimeError):
    """Raised when protected mode is enabled without valid credential records."""


class PromptInjectionError(RuntimeError):
    """Raised when a user query attempts to override advisory policy."""


@dataclass(frozen=True)
class RateLimitPolicy:
    requests: int
    window_seconds: int


@dataclass
class OtpChallenge:
    email: str
    code_hash: str
    role: Role
    expires_at: float
    attempts: int = 0


@dataclass
class SessionRecord:
    token: str
    principal: Principal
    expires_at: float


def sanitize_user_query(query: str) -> str:
    """Strip control characters and refuse clear instruction-override attempts."""

    cleaned = "".join(ch for ch in query if ch == "\n" or ch == "\t" or ord(ch) >= 32).strip()
    if len(cleaned) < 3:
        raise PromptInjectionError("Query is empty after sanitisation.")
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            raise PromptInjectionError(
                "Query looks like an instruction-override attempt and was refused."
            )
    return cleaned[:1_000]


def extract_request_credential(request: Request) -> str:
    """Accept either X-API-Key or Authorization: Bearer for session/API-key auth."""

    supplied = (request.headers.get("X-API-Key") or "").strip()
    if supplied:
        return supplied
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


class ApiKeyAuthorizer:
    """Verifies environment-provided API keys and enforces roles/assignments."""

    def __init__(
        self,
        *,
        auth_required: bool,
        credential_json: str,
        environment: str,
        farmer_region_lookup: Callable[[str], str | None] | None = None,
        registered_farmer_lookup: Callable[[str], dict[str, Any] | None] | None = None,
        session_ttl_seconds: int = 12 * 60 * 60,
        session_store_path: Path | None = None,
    ) -> None:
        self.auth_required = auth_required
        self.environment = environment.lower()
        self._credentials = self._parse_credentials(credential_json)
        self._farmer_region_lookup = farmer_region_lookup
        self._registered_farmer_lookup = registered_farmer_lookup
        self._session_ttl_seconds = session_ttl_seconds
        self._session_store_path = session_store_path
        self._sessions: dict[str, SessionRecord] = {}
        self._otp_challenges: dict[str, OtpChallenge] = {}
        self._dynamic_assignments: dict[str, set[str]] = defaultdict(set)
        self._lock = RLock()
        if self.auth_required and not self._credentials:
            raise SecurityConfigurationError(
                "AUTH_REQUIRED needs at least one AUTH_PRINCIPALS_JSON credential."
            )
        if self.environment != "development" and not self.auth_required:
            raise SecurityConfigurationError(
                "AUTH_REQUIRED must be enabled outside the development environment."
            )
        self._load_persisted_sessions()

    @staticmethod
    def _parse_credentials(credential_json: str) -> list[ApiKeyCredential]:
        if not credential_json.strip():
            return []
        try:
            raw_credentials = json.loads(credential_json)
            return TypeAdapter(list[ApiKeyCredential]).validate_python(raw_credentials)
        except (json.JSONDecodeError, ValidationError) as error:
            raise SecurityConfigurationError("AUTH_PRINCIPALS_JSON is not a valid credential list.") from error

    def set_farmer_region_lookup(self, lookup: Callable[[str], str | None]) -> None:
        self._farmer_region_lookup = lookup

    def set_registered_farmer_lookup(
        self, lookup: Callable[[str], dict[str, Any] | None]
    ) -> None:
        self._registered_farmer_lookup = lookup

    def assign_farmer_to_subject(self, subject: str, farmer_id: str) -> None:
        with self._lock:
            self._dynamic_assignments[subject].add(farmer_id)

    def hydrate_assignments(self, farmers: list[dict[str, Any]]) -> None:
        """Reload officer↔farmer links from durable registered-farmer records."""

        with self._lock:
            for farmer in farmers:
                farmer_id = str(farmer.get("farmer_id") or "")
                if not farmer_id:
                    continue
                state = str(farmer.get("state") or "")
                assigned = list(farmer.get("assigned_officer_subjects") or [])
                for subject in assigned:
                    self._dynamic_assignments[str(subject)].add(farmer_id)
                if state:
                    for subject in self.subjects_for_region(state):
                        self._dynamic_assignments[subject].add(farmer_id)

    def subjects_for_region(self, region: str, role: Role = Role.EXTENSION_OFFICER) -> list[str]:
        subjects: list[str] = []
        for credential in self._credentials:
            if role not in credential.roles:
                continue
            if credential.allowed_regions and region in credential.allowed_regions:
                subjects.append(credential.subject)
        return subjects

    def _effective_allowed_farmer_ids(self, credential: ApiKeyCredential) -> frozenset[str] | None:
        if Role.SYSTEM_ADMIN in credential.roles:
            return None
        allowed: set[str] = set(credential.allowed_farmer_ids or ())
        allowed.update(self._dynamic_assignments.get(credential.subject, set()))
        return frozenset(allowed) if allowed else frozenset()

    def _principal_from_credential(
        self,
        credential: ApiKeyCredential,
        *,
        authentication_method: Literal["api_key", "session_token", "otp"] = "api_key",
    ) -> Principal:
        return Principal(
            subject=credential.subject,
            roles=credential.roles,
            allowed_farmer_ids=self._effective_allowed_farmer_ids(credential),
            allowed_regions=credential.allowed_regions,
            authentication_method=authentication_method,
        )

    def principal_for_registered_farmer(
        self,
        farmer: dict[str, Any],
        *,
        authentication_method: Literal["api_key", "session_token", "otp"] = "session_token",
    ) -> Principal:
        farmer_id = str(farmer["farmer_id"])
        return Principal(
            subject=f"farmer:{farmer_id}",
            roles=frozenset({Role.FARMER}),
            allowed_farmer_ids=frozenset({farmer_id}),
            allowed_regions=None,
            authentication_method=authentication_method,
        )

    def authenticate(self, request: Request) -> Principal:
        if not self.auth_required:
            return Principal(
                subject="local-development-bypass",
                roles=frozenset(Role),
                authentication_method="development_bypass",
            )

        supplied_key = extract_request_credential(request)
        if not supplied_key:
            raise AuthenticationError("A valid X-API-Key or Bearer session token is required.")

        with self._lock:
            session = self._sessions.get(supplied_key)
            if session is not None:
                if session.expires_at < time():
                    self._sessions.pop(supplied_key, None)
                    self._persist_sessions_unlocked()
                    raise AuthenticationError("The session token has expired.")
                return session.principal

        for credential in self._credentials:
            if secrets.compare_digest(supplied_key, credential.api_key):
                return self._principal_from_credential(credential)

        raise AuthenticationError("The supplied API key is not valid.")

    def issue_session(self, principal: Principal) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = SessionRecord(
                token=token,
                principal=principal.model_copy(
                    update={"authentication_method": "session_token"}
                ),
                expires_at=time() + self._session_ttl_seconds,
            )
            self._persist_sessions_unlocked()
        return token

    def revoke_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)
            self._persist_sessions_unlocked()

    def _load_persisted_sessions(self) -> None:
        if self._session_store_path is None or not self._session_store_path.exists():
            return
        try:
            payload = json.loads(self._session_store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, list):
            return
        now = time()
        with self._lock:
            for item in payload:
                if not isinstance(item, dict):
                    continue
                token = str(item.get("token") or "")
                expires_at = item.get("expires_at")
                principal_raw = item.get("principal")
                if not token or not isinstance(expires_at, (int, float)) or expires_at < now:
                    continue
                if not isinstance(principal_raw, dict):
                    continue
                try:
                    principal = Principal.model_validate(principal_raw)
                except ValidationError:
                    continue
                self._sessions[token] = SessionRecord(
                    token=token,
                    principal=principal,
                    expires_at=float(expires_at),
                )

    def _persist_sessions_unlocked(self) -> None:
        if self._session_store_path is None:
            return
        now = time()
        payload = [
            {
                "token": session.token,
                "expires_at": session.expires_at,
                "principal": session.principal.model_dump(mode="json"),
            }
            for session in self._sessions.values()
            if session.expires_at >= now
        ]
        try:
            self._session_store_path.parent.mkdir(parents=True, exist_ok=True)
            self._session_store_path.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Session persistence is best-effort for local/hackathon restarts.
            return

    def find_credential_by_email(self, email: str) -> ApiKeyCredential | None:
        normalised = email.strip().lower()
        for credential in self._credentials:
            if credential.email and credential.email.strip().lower() == normalised:
                return credential
        return None

    def start_otp_challenge(self, *, email: str, role: Role) -> str:
        """Create an OTP challenge and return the plaintext code for local demo delivery."""

        code = f"{secrets.randbelow(1_000_000):06d}"
        with self._lock:
            self._otp_challenges[email.strip().lower()] = OtpChallenge(
                email=email.strip().lower(),
                code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
                role=role,
                expires_at=time() + 600,
                attempts=0,
            )
        return code

    def verify_otp(self, *, email: str, code: str, role: Role) -> tuple[Principal, str]:
        key = email.strip().lower()
        with self._lock:
            challenge = self._otp_challenges.get(key)
            if challenge is None or challenge.expires_at < time():
                self._otp_challenges.pop(key, None)
                raise AuthenticationError("OTP challenge is missing or expired.")
            if challenge.role is not role:
                raise AuthorizationError("OTP role does not match the requested login role.")
            challenge.attempts += 1
            if challenge.attempts > 5:
                self._otp_challenges.pop(key, None)
                raise AuthenticationError("Too many OTP attempts.")
            expected = challenge.code_hash
            provided = hashlib.sha256(code.strip().encode("utf-8")).hexdigest()
            if not secrets.compare_digest(expected, provided):
                raise AuthenticationError("OTP code is not valid.")
            self._otp_challenges.pop(key, None)

        credential = self.find_credential_by_email(email)
        if credential is not None and role in credential.roles:
            principal = self._principal_from_credential(credential, authentication_method="otp")
            token = self.issue_session(principal)
            return principal, token

        if role is Role.FARMER and self._registered_farmer_lookup is not None:
            farmer = self._registered_farmer_lookup(email)
            if farmer is not None:
                principal = self.principal_for_registered_farmer(farmer, authentication_method="otp")
                token = self.issue_session(principal)
                return principal, token

        raise AuthenticationError("No principal is registered for this email and role.")

    def login_with_api_key(self, api_key: str, expected_role: Role | None = None) -> tuple[Principal, str]:
        for credential in self._credentials:
            if secrets.compare_digest(api_key, credential.api_key):
                if expected_role is not None and expected_role not in credential.roles:
                    raise AuthorizationError("This API key does not match the selected role.")
                principal = self._principal_from_credential(credential)
                return principal, self.issue_session(principal)
        raise AuthenticationError("The supplied API key is not valid.")

    @staticmethod
    def require_roles(principal: Principal, allowed_roles: frozenset[Role]) -> None:
        if not principal.roles.intersection(allowed_roles):
            raise AuthorizationError("This principal does not have the required role.")

    def require_farmer_assignment(self, principal: Principal, farmer_id: str) -> None:
        if principal.authentication_method == "development_bypass" or Role.SYSTEM_ADMIN in principal.roles:
            return
        if principal.allowed_farmer_ids is not None and farmer_id in principal.allowed_farmer_ids:
            return
        if Role.FARMER in principal.roles and Role.EXTENSION_OFFICER not in principal.roles:
            raise AuthorizationError("This principal is not assigned to the requested farmer.")
        if principal.allowed_regions and self._farmer_region_lookup is not None:
            region = self._farmer_region_lookup(farmer_id)
            if region is not None and region in principal.allowed_regions:
                return
        raise AuthorizationError("This principal is not assigned to the requested farmer.")

    def visible_farmer_ids(
        self,
        principal: Principal,
        catalog: list[tuple[str, str]],
    ) -> list[str] | None:
        """Return None for unrestricted access, otherwise the visible farmer IDs."""

        if principal.authentication_method == "development_bypass" or Role.SYSTEM_ADMIN in principal.roles:
            return None
        # Farmers are scoped only to explicitly assigned farmer IDs.
        if Role.FARMER in principal.roles and Role.EXTENSION_OFFICER not in principal.roles:
            return sorted(principal.allowed_farmer_ids or ())
        visible: set[str] = set()
        if principal.allowed_farmer_ids:
            visible.update(principal.allowed_farmer_ids)
        if principal.allowed_regions:
            for farmer_id, region in catalog:
                if region in principal.allowed_regions:
                    visible.add(farmer_id)
        return sorted(visible)


class SlidingWindowRateLimiter:
    """Thread-safe, bounded in-memory rate limiting for the local API process."""

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        role_policies: dict[Role, RateLimitPolicy] | None = None,
        anonymous_policy: RateLimitPolicy | None = None,
    ) -> None:
        self.policy = policy
        self.role_policies = role_policies or {}
        self.anonymous_policy = anonymous_policy or RateLimitPolicy(
            requests=max(20, policy.requests // 3),
            window_seconds=policy.window_seconds,
        )
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def _policy_for(self, request: Request) -> RateLimitPolicy:
        principal = getattr(request.state, "principal", None)
        if principal is None:
            return self.anonymous_policy
        for role in (Role.FARMER, Role.EXTENSION_OFFICER, Role.SYSTEM_ADMIN):
            if role in principal.roles and role in self.role_policies:
                return self.role_policies[role]
        return self.policy

    def check(self, request: Request) -> None:
        policy = self._policy_for(request)
        client_host = request.client.host if request.client else "unknown"
        key_fingerprint = hashlib.sha256(
            extract_request_credential(request).encode("utf-8") or b"anonymous"
        ).hexdigest()[:16]
        key = f"{client_host}:{key_fingerprint}"
        now = time()
        cutoff = now - policy.window_seconds

        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= policy.requests:
                raise RateLimitExceededError("Rate limit exceeded; retry after the configured window.")
            bucket.append(now)
