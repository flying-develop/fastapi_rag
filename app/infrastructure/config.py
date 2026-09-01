"""Application configuration loaded from environment variables (.env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings, sourced from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "ai-app-python"
    log_level: str = "DEBUG"

    # Database (used starting from the "Фундамент работы с БД" milestone)
    database_url: str = "postgresql+asyncpg://projects:projects@localhost:5432/ai_app"

    # Redis (used starting from the ARQ background-jobs milestone)
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant (used starting from the RAG milestones)
    qdrant_url: str = "http://localhost:6333"

    # LLM provider (used starting from the "Диалоги с LLM" milestone)
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read once per process)."""
    return Settings()
