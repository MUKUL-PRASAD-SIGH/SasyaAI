"""Production telemetry setup kept outside the advisory business logic."""

from __future__ import annotations

import logging

from app.core.config import Settings


class ObservabilityConfigurationError(RuntimeError):
    """Production telemetry could not be configured safely."""


def configure_observability(app, settings: Settings) -> None:
    """Attach OpenTelemetry tracing and a Prometheus scrape endpoint in production.

    Export failures never disclose prompts, consent payloads, tokens, or farmer
    profile fields. Request-level spans receive only route/status metadata from
    the FastAPI instrumentation layer.
    """

    if settings.runtime_mode != "production":
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from prometheus_client import make_asgi_app
    except ImportError as error:  # pragma: no cover - executed in production installation only
        raise ObservabilityConfigurationError(
            "Production telemetry dependencies are not installed."
        ) from error

    try:
        resource = Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": settings.service_version,
                "deployment.environment": settings.app_environment,
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        app.mount("/metrics", make_asgi_app())
    except Exception as error:
        logging.getLogger(__name__).exception("Production telemetry configuration failed.")
        raise ObservabilityConfigurationError("Production telemetry initialisation failed.") from error
