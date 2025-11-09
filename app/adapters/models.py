"""Domain models for channel adapters."""

from uuid import UUID

from pydantic import BaseModel, Field


class ReceivedMessage(BaseModel):
    """Message received from an external channel."""

    content: str = Field(..., description="The actual message text")
    sender_id: str = Field(..., description="User identifier in the channel")
    conversation_id: UUID | None = Field(None, description="ID to link back to conversation thread")
    thread_id: str = Field(..., description="Channel-specific thread/conversation ID")
    metadata: dict = Field(
        default_factory=dict,
        description="Channel-specific data (attachments, reactions, etc.)",
    )


class RichMessage(BaseModel):
    """Message with rich formatting capabilities."""

    text: str = Field(..., description="Main text content")
    fallback_text: str = Field(
        ..., description="Plain text fallback for clients without rich formatting support"
    )
    formatting: dict = Field(
        default_factory=dict, description="Formatting details (markdown, html, etc.)"
    )


class InteractiveMessage(BaseModel):
    """Message with interactive elements (buttons, forms, etc.)."""

    text: str = Field(..., description="Message text")
    buttons: list[dict] = Field(
        default_factory=list,
        description="List of buttons with action_id and value",
    )
    metadata: dict = Field(
        default_factory=dict, description="Additional metadata for interactive elements"
    )


class InteractionResponse(BaseModel):
    """Response to user interaction with interactive elements."""

    conversation_id: UUID = Field(..., description="Associated conversation ID")
    action_id: str = Field(..., description="The action that was triggered")
    value: str = Field(..., description="The value associated with the action")
    user_id: str = Field(..., description="The user who triggered the interaction")
