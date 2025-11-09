"""Agent runner for Pydantic AI framework."""

from collections.abc import AsyncIterator
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from app.runners.base import AgentRunner, RunnerCapabilities
from app.runners.models import (
    AgentMessage,
    ExecutionContext,
    ExecutionResult,
    MessageRole,
    StreamChunk,
)


class PydanticAIRunner(AgentRunner):
    """Agent runner for Pydantic AI framework."""

    def __init__(self, agent: Agent, tools: list[Any] | None = None):
        super().__init__(tools)
        self.agent = agent

        # Register tools with Pydantic AI agent
        if self.tools:
            for tool in self.tools:
                self.agent.tool(tool)

    @property
    def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            supports_streaming=True,
            supports_tool_use=len(self.agent._function_tools) > 0,
            supports_vision=False,  # Depends on model
            supports_system_prompt_override=True,
            context_window=None,  # Model-dependent
            max_output_tokens=None,  # Model-dependent
            supports_conversation_history=True,
            supports_async_execution=True,
        )

    async def execute_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Execute with streaming via Pydantic AI."""
        await self.validate_execution(streaming=True, message_history=message_history)

        # Convert message history to Pydantic AI format
        messages = self._convert_messages(message_history or [])

        # Build run parameters
        run_params = {}
        if context and context.system_prompt:
            run_params["system_prompt"] = context.system_prompt
        if context and context.max_tokens:
            run_params["max_tokens"] = context.max_tokens

        # Stream execution
        async with self.agent.run_stream(
            prompt,
            message_history=messages,
            **run_params,
        ) as response:
            async for chunk in response.stream_text():
                yield StreamChunk(content=chunk, metadata={"raw_chunk": chunk})

    async def execute_non_streaming(
        self,
        prompt: str,
        message_history: list[AgentMessage] | None = None,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        """Execute without streaming via Pydantic AI."""
        await self.validate_execution(streaming=False, message_history=message_history)

        # Convert message history
        messages = self._convert_messages(message_history or [])

        # Build run parameters
        run_params = {}
        if context and context.system_prompt:
            run_params["system_prompt"] = context.system_prompt
        if context and context.max_tokens:
            run_params["max_tokens"] = context.max_tokens

        # Execute
        result = await self.agent.run(
            prompt,
            message_history=messages,
            **run_params,
        )

        return ExecutionResult(
            content=str(result.data),
            finish_reason="complete",
            token_usage=result.usage() if hasattr(result, "usage") else None,
            metadata={"raw_result": result},
        )

    def _convert_messages(self, messages: list[AgentMessage]) -> list[ModelRequest | ModelResponse]:
        """Convert standard AgentMessage to Pydantic AI Message format.

        Converts AgentMessage objects to Pydantic AI's ModelRequest/ModelResponse format.
        ModelRequest represents user/system messages, ModelResponse represents assistant messages.
        """
        converted = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                # Create a ModelRequest with UserPromptPart for user messages
                converted.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
            elif msg.role == MessageRole.ASSISTANT:
                # Create a ModelResponse with TextPart for assistant messages
                converted.append(ModelResponse(parts=[TextPart(content=msg.content)]))
            # System messages are handled via system_prompt parameter in run()
        return converted

    async def register_tool(self, tool: Any) -> None:
        """Register a tool with the Pydantic AI agent."""
        self.agent.tool(tool)
        self.tools.append(tool)

    async def cleanup(self) -> None:
        """Clean up resources (no-op for Pydantic AI runner)."""
        pass
