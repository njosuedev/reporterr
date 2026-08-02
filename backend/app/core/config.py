"""Application configuration, loaded from environment variables (.env)."""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──────────────────────────────────────────
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "VAT Report Analyzer Rwanda"
    API_V1_PREFIX: str = "/api"
    TZ: str = "Africa/Kigali"

    # ── CORS ─────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Uploads ──────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".xlsx", ".xls")

    # ── VAT ──────────────────────────────────────────────
    VAT_RATE: float = 0.18

    # ── Rate limiting ────────────────────────────────────
    RATE_LIMIT_GENERATE: str = "20/minute"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
