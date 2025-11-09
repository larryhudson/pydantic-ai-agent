"""Mock runner for testing."""

from collections.abc import AsyncIterator
from typing import Any

from app.runners.base import AgentRunner, RunnerCapabilities
from app.runners.models import AgentMessage, ExecutionContext, ExecutionResult, StreamChunk


class MockRunner(AgentRunner):
    """Mock runner for testing."""

    def __init__(
        self,
        mock_response: str = "Mock response",
        should_stream: bool = True,
        tools: list[Any] | None = None,
    ):
        super().__init__(tools)
        self.mock_response = mock_response
        self.should_stream = should_stream
        self.call_count = 0
        self.last_prompt = None
        self.last_history = None

    @property
    def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            supports_streaming=self.should_stream,
            supports_tool_use=bool(self.tools),
            supports_vision=False,
            supports_conversation_history=True,
        )

    async def execute_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute streaming with mock response."""
        await self.validate_execution(streaming=True, message_history=message_history)

        self.call_count += 1
        self.last_prompt = prompt
        self.last_history = message_history

        # Simulate streaming by chunking response
        for char in self.mock_response:
            yield StreamChunk(content=char)

    async def execute_non_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute non-streaming with mock response."""
        await self.validate_execution(streaming=False, message_history=message_history)

        self.call_count += 1
        self.last_prompt = prompt
        self.last_history = message_history

        return ExecutionResult(
            content=self.mock_response,
            finish_reason="complete",
        )

    async def cleanup(self) -> None:
        """Clean up resources (no-op for mock runner)."""
        pass
