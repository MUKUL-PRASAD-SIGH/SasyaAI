"""Runtime configuration for the local demonstrator."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SasyaAI"
    app_environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auth_required: bool = False
    auth_principals_json: str = ""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    retention_days: int = 30
    safety_rule_set_version: str = "synthetic-demo-2026.07"

    # Optional production-oriented integrations. The local demonstrator works
    # without them and uses deterministic seed data instead.
    lyzr_api_key: str = ""
    lyzr_workflow_id: str = ""
    lyzr_base_url: str = "https://api.lyzr.ai"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    hitl_confidence_threshold: float = 0.70

    @property
    def seed_data_dir(self) -> Path:
        return ROOT_DIR / "data" / "seed"

    @property
    def runtime_dir(self) -> Path:
        return ROOT_DIR / "var"


@lru_cache
def get_settings() -> Settings:
    return Settings()
