from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: Literal["development", "demo", "test", "production"] = "development"
    seed_demo_user: bool = True
    database_url: str = f"sqlite:///{ROOT / 'projecttrace.db'}"
    redis_url: str = "redis://127.0.0.1:6379/0"
    queue_mode: Literal["local", "rq"] = "local"
    secret_key: str = "development-only-not-a-production-secret"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    llm_provider: Literal["offline", "openai"] = "offline"
    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "hashing-v1"
    vector_store: Literal["faiss", "pgvector"] = "faiss"
    max_upload_mb: int = Field(50, ge=1, le=100)
    max_extracted_mb: int = Field(200, ge=1, le=1000)
    max_file_count: int = Field(10000, ge=1, le=50000)
    max_text_file_mb: int = Field(2, ge=1, le=10)
    max_chunks: int = Field(20000, ge=1, le=100000)
    max_compression_ratio: int = Field(150, ge=1)
    upload_retention_hours: int = Field(24, ge=1, le=720)
    session_hours: int = Field(24, ge=1, le=168)
    storage_dir: Path = ROOT / ".storage"
    api_rate_per_minute: int = 120
    ai_rate_per_minute: int = 10
    import_rate_per_minute: int = 5
    auth_rate_per_minute: int = 10
    job_timeout_seconds: int = 600

    @property
    def origins(self):
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_production(self):
        if "*" in self.origins:
            raise ValueError("Explicit CORS origins required; wildcard is prohibited.")
        if self.llm_provider != "offline" and not self.llm_api_key:
            raise ValueError("LLM_API_KEY required when external provider is enabled.")
        if self.app_env == "production":
            if (
                len(self.secret_key) < 32
                or "change-this" in self.secret_key
                or "development" in self.secret_key
            ):
                raise ValueError(
                    "Production requires a random SECRET_KEY with at least 32 characters."
                )
            if not self.database_url.startswith("postgresql") or self.queue_mode != "rq":
                raise ValueError("Production requires PostgreSQL and QUEUE_MODE=rq.")
            if any(not x.startswith("https://") for x in self.origins):
                raise ValueError("Production CORS origins must use HTTPS.")
        self.storage_dir = (
            (ROOT / self.storage_dir).resolve()
            if not self.storage_dir.is_absolute()
            else self.storage_dir.resolve()
        )
        return self


@lru_cache
def settings():
    return Settings()
