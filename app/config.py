"""Application configuration and settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    # Application
    app_name: str = "AI Agent Platform"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_platform"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600  # 1 hour in seconds

    # AI Model
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    default_model: str = "openai:gpt-4"

    # Email (Mailgun)
    mailgun_api_key: str | None = None
    mailgun_domain: str | None = None
    mailgun_from_email: str = "noreply@aiagent.platform"

    # Slack Adapter
    slack_bot_token: str | None = None
    slack_signing_secret: str | None = None
    slack_webhook_url: str | None = None

    # Background Jobs
    arq_redis_url: str = "redis://localhost:6379"
    max_worker_jobs: int = 10

    # Scheduler
    scheduler_timezone: str = "UTC"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
