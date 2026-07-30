from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
FARMERS_DIR = ROOT_DIR / "data" / "seed" / "farmers"
KB_DIR = ROOT_DIR / "data" / "seed" / "kb"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    lyzr_api_key: str = ""
    lyzr_workflow_id: str = ""
    lyzr_base_url: str = "https://api.lyzr.ai"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    hitl_queue_path: str = "infra/hitl/queue.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
