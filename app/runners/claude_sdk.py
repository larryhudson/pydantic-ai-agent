"""Agent runner for Claude Agent SDK (future implementation)."""

from collections.abc import AsyncIterator
from typing import Any

from app.runners.base import AgentRunner, RunnerCapabilities
from app.runners.models import (
    AgentMessage,
    ExecutionContext,
    ExecutionResult,
    StreamChunk,
)


class ClaudeAgentSDKRunner(AgentRunner):
    """Agent runner for Claude Agent SDK (placeholder for future implementation)."""

    def __init__(self, api_key: str, tools: list[Any] | None = None):
        super().__init__(tools)
        self.api_key = api_key
        # Initialize Claude Agent SDK client
        # TODO: Implement Claude Agent SDK integration

    @property
    def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            supports_streaming=True,
            supports_tool_use=True,
            supports_vision=True,
            supports_system_prompt_override=True,
            context_window=200_000,
            max_output_tokens=8_192,
            supports_conversation_history=True,
            supports_async_execution=True,
        )

    async def execute_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute with streaming (not yet implemented)."""
        raise NotImplementedError("Claude Agent SDK runner not yet implemented")

    async def execute_non_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute without streaming (not yet implemented)."""
        raise NotImplementedError("Claude Agent SDK runner not yet implemented")

    async def cleanup(self) -> None:
        """Clean up resources (not yet implemented)."""
        pass
