"""Application configuration and settings."""

from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.runners.base import RunnerConfigurationError, RunnerType


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

    # Agent Runner
    agent_runner_type: RunnerType = RunnerType.PYDANTIC_AI


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def create_agent_runner(
    runner_type: RunnerType | None = None,
    tools: list[Any] | None = None,
) -> Any:
    """Factory function to create agent runners.

    Args:
        runner_type: Type of runner to create (defaults to config setting)
        tools: Optional tools to provide to the runner

    Returns:
        Configured AgentRunner instance

    Raises:
        RunnerConfigurationError: If runner type invalid or dependencies missing
    """
    from app.runners.pydantic_ai import PydanticAIRunner

    settings = get_settings()
    runner_type = runner_type or settings.agent_runner_type

    if runner_type == RunnerType.PYDANTIC_AI:
        try:
            from pydantic_ai import Agent
        except ImportError as e:
            raise RunnerConfigurationError(
                "Pydantic AI not installed. Install with: pip install pydantic-ai"
            ) from e

        agent = Agent(
            model=settings.default_model,
            system_prompt=(
                "You are a helpful AI assistant. Provide clear, concise, "
                "and accurate responses to user queries."
            ),
        )
        return PydanticAIRunner(agent=agent, tools=tools)

    elif runner_type == RunnerType.CLAUDE_SDK:
        try:
            from app.runners.claude_sdk import ClaudeAgentSDKRunner
        except ImportError as e:
            raise RunnerConfigurationError(
                "Claude Agent SDK not installed. Install with: pip install claude-agent-sdk"
            ) from e

        if not settings.anthropic_api_key:
            raise RunnerConfigurationError("ANTHROPIC_API_KEY required for Claude SDK runner")

        return ClaudeAgentSDKRunner(
            api_key=settings.anthropic_api_key,
            tools=tools,
        )

    else:
        raise RunnerConfigurationError(f"Unknown runner type: {runner_type}")
