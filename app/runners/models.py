"""Domain models for agent runners."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Standard message roles across all frameworks."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AgentMessage(BaseModel):
    """Standardized message format for all runners."""

    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class ToolCall(BaseModel):
    """Tool call information."""

    id: str
    name: str
    arguments: dict[str, Any]


class StreamChunk(BaseModel):
    """Chunk of streaming response."""

    content: str = ""
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Complete execution result for non-streaming."""

    content: str
    tool_calls: list[ToolCall] | None = None
    finish_reason: str
    token_usage: dict[str, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(BaseModel):
    """Context for agent execution."""

    conversation_id: UUID | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    additional_params: dict[str, Any] = Field(default_factory=dict)
