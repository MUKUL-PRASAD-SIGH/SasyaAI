"""Live, source-attributed tool adapters used in production mode only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.services.resilience import CircuitBreaker, ProviderUnavailableError, retry_provider_call


class ToolDataUnavailableError(ProviderUnavailableError):
    """A live source failed; callers must not replace it with seed data in production."""


class LiveDataGateway:
    """Timeout-bounded external data boundary with provenance on every result."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.tool_timeout_seconds)
        self.weather_breaker = CircuitBreaker()
        self.market_breaker = CircuitBreaker()
        self.agristack_breaker = CircuitBreaker()

    @staticmethod
    def _snapshot(provider: str, data: dict[str, Any], *, source_id: str) -> dict[str, Any]:
        return {
            "provider": provider,
            "source_record_id": source_id,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "freshness": "live",
            "data": data,
        }

    def _request_json(
        self,
        *,
        breaker: CircuitBreaker,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str | float] | None = None,
    ) -> dict[str, Any]:
        def call() -> dict[str, Any]:
            response = self.client.request(method, url, headers=headers, params=params)
            response.raise_for_status()
            decoded = response.json()
            if not isinstance(decoded, dict):
                raise ValueError("Live provider response must be a JSON object.")
            return decoded

        try:
            return retry_provider_call(
                call,
                breaker=breaker,
                retries=self.settings.tool_max_retries,
                retryable=(httpx.HTTPError, ValueError),
            )
        except ProviderUnavailableError as error:
            raise ToolDataUnavailableError("A required live tool is unavailable.") from error

    def weather(self, farmer: dict[str, Any]) -> dict[str, Any]:
        location = farmer.get("location", {})
        try:
            latitude = float(location["latitude"])
            longitude = float(location["longitude"])
        except (KeyError, TypeError, ValueError) as error:
            raise ToolDataUnavailableError("Live weather requires an authorised farm latitude and longitude.") from error
        payload = self._request_json(
            breaker=self.weather_breaker,
            method="GET",
            url=f"{self.settings.weather_api_base_url.rstrip('/')}/forecast",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,precipitation,wind_speed_10m",
                "daily": "precipitation_probability_max,weather_code",
                "forecast_days": 2,
                "timezone": "auto",
            },
        )
        current = payload.get("current", {})
        daily = payload.get("daily", {})
        data = {
            "temperature_c": current.get("temperature_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "max_precipitation_probability": (daily.get("precipitation_probability_max") or [None])[0],
            "weather_code": (daily.get("weather_code") or [None])[0],
        }
        return self._snapshot("open_meteo", data, source_id=f"{latitude:.4f},{longitude:.4f}")

    def market(self, farmer: dict[str, Any], query: str) -> dict[str, Any]:
        """Read a startup-configured market connector; the provider schema stays outside prompts."""

        crop = str(farmer.get("digital_twin", {}).get("current_crop", ""))
        payload = self._request_json(
            breaker=self.market_breaker,
            method="GET",
            url=self.settings.market_api_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {self.settings.market_api_key}"},
            params={"district": str(farmer.get("district", "")), "crop": crop, "query": query[:200]},
        )
        return self._snapshot("configured_market_provider", payload, source_id=f"{farmer['farmer_id']}:{crop}")

    def agristack_farmer_context(self, farmer_id: str) -> dict[str, Any]:
        """Refresh source context through the approved AgriStack gateway contract.

        The exact service path is configurable at the gateway level; credentials
        are never sent to the model or returned from this adapter.
        """

        payload = self._request_json(
            breaker=self.agristack_breaker,
            method="GET",
            url=(
                f"{self.settings.agristack_api_base_url.rstrip('/')}/farmers/"
                f"{quote(farmer_id, safe='')}/context"
            ),
            headers={"Authorization": f"Bearer {self.settings.agristack_access_token}"},
        )
        return self._snapshot("agristack", payload, source_id=farmer_id)

    def agristack_consent(self, farmer_id: str, purpose: str) -> dict[str, Any] | None:
        """Read a live consent receipt before any production profile or memory access.

        AgriStack gateway deployments can wrap their upstream response in a
        ``consent`` object; supporting both shapes keeps that gateway contract
        explicit without allowing the rest of the application to parse it.
        """

        payload = self._request_json(
            breaker=self.agristack_breaker,
            method="GET",
            url=(
                f"{self.settings.agristack_api_base_url.rstrip('/')}/consents/"
                f"{quote(farmer_id, safe='')}"
            ),
            headers={"Authorization": f"Bearer {self.settings.agristack_access_token}"},
            params={"purpose": purpose},
        )
        if payload.get("found") is False:
            return None
        consent = payload.get("consent", payload)
        if not isinstance(consent, dict):
            raise ToolDataUnavailableError("AgriStack consent response has an invalid contract.")
        return consent
