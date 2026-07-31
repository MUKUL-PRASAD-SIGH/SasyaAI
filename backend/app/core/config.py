"""Runtime configuration for demo and production SasyaAI deployments."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SasyaAI"
    app_environment: str = "development"
    runtime_mode: Literal["demo", "production"] = "demo"
    production_data_mode: Literal["live", "synthetic"] = "live"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auth_required: bool = False
    auth_principals_json: str = ""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_farmer_requests: int = 60
    rate_limit_officer_requests: int = 120
    rate_limit_admin_requests: int = 240
    google_oauth_enabled: bool = False
    retention_days: int = 30
    safety_rule_set_version: str = "synthetic-demo-2026.07"

    # LLM runtime. Gemini is the initial provider because it supports a free
    # development tier, multilingual generation, and JSON-mode responses. The
    # provider boundary deliberately keeps a later Vertex/OpenAI/self-hosted
    # migration from leaking through the advisory workflow.
    llm_provider: Literal["gemini"] = "gemini"
    gemini_api_key: str = ""
    # Pin the validated lightweight production model by default. Individual
    # deployments can override GEMINI_MODEL after validating access and quota.
    gemini_model: str = "gemini-3.1-flash-lite"
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2

    # Durable production data stores. Both are mandatory in production mode;
    # demo mode remains self-contained and intentionally uses local fixtures.
    database_url: str = ""
    lyzr_api_key: str = ""
    lyzr_workflow_id: str = ""
    lyzr_base_url: str = "https://api.lyzr.ai"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_cache_dir: str = ""

    # Live-tool configuration. Open-Meteo is keyless and used only as a live
    # weather signal; market and AgriStack are enabled only after the startup
    # team receives the provider-specific credentials and endpoint contracts.
    weather_api_base_url: str = "https://api.open-meteo.com/v1"
    market_api_base_url: str = ""
    market_api_key: str = ""
    agristack_api_base_url: str = ""
    agristack_access_token: str = ""
    tool_timeout_seconds: float = 8.0
    tool_max_retries: int = 2

    # OTLP export is optional when the deployment exposes the local Prometheus
    # scrape endpoint through a collector or sidecar. The application still
    # instruments production requests when this value is empty.
    otel_exporter_otlp_endpoint: str = ""
    service_version: str = "0.2.0"

    hitl_confidence_threshold: float = 0.70

    @property
    def seed_data_dir(self) -> Path:
        return ROOT_DIR / "data" / "seed"

    @property
    def runtime_dir(self) -> Path:
        return ROOT_DIR / "var"

    def production_configuration_errors(self) -> list[str]:
        """Return safe startup diagnostics without ever printing secrets."""

        if self.runtime_mode != "production":
            return []

        required = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "DATABASE_URL": self.database_url,
            "QDRANT_URL": self.qdrant_url,
        }
        if self.production_data_mode == "live":
            required.update(
                {
                    "AGRISTACK_API_BASE_URL": self.agristack_api_base_url,
                    "AGRISTACK_ACCESS_TOKEN": self.agristack_access_token,
                    "MARKET_API_BASE_URL": self.market_api_base_url,
                    "MARKET_API_KEY": self.market_api_key,
                }
            )
        errors = [name for name, value in required.items() if not value.strip()]
        if not self.auth_required:
            errors.append("AUTH_REQUIRED=true")
        elif not self.auth_principals_json.strip():
            errors.append("AUTH_PRINCIPALS_JSON")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
