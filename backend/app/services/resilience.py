"""Small, dependency-free resilience primitives for outbound providers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from time import monotonic, sleep
from typing import TypeVar

T = TypeVar("T")


class ProviderUnavailableError(RuntimeError):
    """Raised when a dependency cannot safely produce a current result."""


@dataclass
class CircuitBreaker:
    """A process-local circuit breaker that fails fast during provider outages."""

    failure_threshold: int = 3
    recovery_seconds: float = 30.0

    def __post_init__(self) -> None:
        self._lock = RLock()
        self._failures = 0
        self._opened_at: float | None = None

    def before_call(self) -> None:
        with self._lock:
            if self._opened_at is None:
                return
            if monotonic() - self._opened_at >= self.recovery_seconds:
                self._opened_at = None
                self._failures = 0
                return
            raise ProviderUnavailableError("Provider circuit is open; retry after recovery.")

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = monotonic()


def retry_provider_call(
    operation: Callable[[], T],
    *,
    breaker: CircuitBreaker,
    retries: int,
    retryable: tuple[type[BaseException], ...],
) -> T:
    """Retry transient provider errors with bounded exponential backoff."""

    breaker.before_call()
    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            value = operation()
        except retryable as error:
            last_error = error
            if attempt == retries:
                breaker.record_failure()
                break
            sleep(min(1.0, 0.15 * (2**attempt)))
        else:
            breaker.record_success()
            return value
    raise ProviderUnavailableError("A required provider did not return a usable response.") from last_error
