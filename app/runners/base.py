"""Base classes and protocols for agent runners."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from app.runners.models import (
    AgentMessage,
    ExecutionContext,
    ExecutionResult,
    StreamChunk,
    ToolCall,
)


class RunnerType(str, Enum):
    """Available agent runner types."""

    PYDANTIC_AI = "pydantic_ai"
    CLAUDE_SDK = "claude_sdk"
    LANGCHAIN = "langchain"


@dataclass
class RunnerCapabilities:
    """Declares what features this runner supports."""

    supports_streaming: bool = True
    supports_tool_use: bool = False
    supports_vision: bool = False
    supports_system_prompt_override: bool = True
    context_window: int | None = None
    max_output_tokens: int | None = None
    supports_conversation_history: bool = True
    supports_async_execution: bool = True


# Exception Hierarchy
class RunnerError(Exception):
    """Base exception for all runner errors."""

    pass


class RunnerNotCapableError(RunnerError):
    """Runner doesn't support requested capability."""

    pass


class RunnerExecutionError(RunnerError):
    """Error during agent execution."""

    pass


class RunnerTimeoutError(RunnerError):
    """Execution timed out."""

    pass


class RunnerConfigurationError(RunnerError):
    """Invalid runner configuration."""

    pass


# Optional Capability Protocols
@runtime_checkable
class ToolCallCapable(Protocol):
    """Runner can execute tool calls."""

    async def register_tool(self, tool: Any) -> None:
        """Register a tool with the runner."""
        ...

    async def execute_tool_call(self, tool_call: ToolCall) -> Any:
        """Execute a specific tool call."""
        ...


@runtime_checkable
class VisionCapable(Protocol):
    """Runner can process images."""

    async def process_image(
        self,
        image_data: str | bytes,
        prompt: str,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Process an image with a prompt."""
        ...


@runtime_checkable
class ResponseFormatCapable(Protocol):
    """Runner can enforce structured output formats."""

    async def set_response_format(self, format_schema: dict[str, Any]) -> None:
        """Set JSON schema for response format."""
        ...


class AgentRunner(ABC):
    """Base class for all agent runners."""

    def __init__(self, tools: list[Any] | None = None):
        """Initialize the runner.

        Args:
            tools: Optional list of tools available to the agent.
                   Format is runner-specific.
        """
        self.tools = tools or []

    @property
    @abstractmethod
    def capabilities(self) -> RunnerCapabilities:
        """Declare what this runner can do."""
        pass

    @abstractmethod
    async def execute_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute with streaming response (chatbot, sidekick patterns).

        Args:
            prompt: The user's input message
            message_history: Previous conversation messages
            context: Execution context (system prompt, params, etc.)

        Yields:
            StreamChunk objects containing incremental responses

        Raises:
            RunnerNotCapableError: If streaming not supported
            RunnerExecutionError: If execution fails
            RunnerTimeoutError: If execution times out
        """
        pass

    @abstractmethod
    async def execute_non_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute without streaming (delegation, scheduled, triggered patterns).

        Args:
            prompt: The user's input message
            message_history: Previous conversation messages
            context: Execution context (system prompt, params, etc.)

        Returns:
            ExecutionResult with complete response

        Raises:
            RunnerExecutionError: If execution fails
            RunnerTimeoutError: If execution times out
        """
        pass

    async def validate_execution(
        self,
        streaming: bool,
        message_history: list[AgentMessage] | None = None,
    ) -> None:
        """Validate that execution is possible with current capabilities.

        Args:
            streaming: Whether streaming execution is requested
            message_history: Message history to validate

        Raises:
            RunnerNotCapableError: If requested features not supported
        """
        if streaming and not self.capabilities.supports_streaming:
            raise RunnerNotCapableError(f"{self.__class__.__name__} does not support streaming")

        if message_history and not self.capabilities.supports_conversation_history:
            raise RunnerNotCapableError(
                f"{self.__class__.__name__} does not support conversation history"
            )

    @asynccontextmanager
    async def session(self):
        """Async context manager for runner lifecycle management.

        Use for resource initialization, cleanup, connection pooling, etc.

        Example:
            async with runner.session():
                result = await runner.execute_non_streaming(...)
        """
        # Default implementation: no-op
        yield self

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources. Called when runner is no longer needed."""
        pass
