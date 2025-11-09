"""Base channel adapter interface and capability protocols."""

from abc import ABC, abstractmethod
from enum import Enum
from uuid import UUID

from app.adapters.models import (
    InteractionResponse,
    InteractiveMessage,
    ReceivedMessage,
    RichMessage,
)


class MessageStyle(str, Enum):
    """Preferred interaction style for this channel."""

    CONVERSATIONAL = "conversational"  # Quick back-and-forth (Slack)
    COMPREHENSIVE = "comprehensive"  # Detailed, batched messages (Email)


class AdapterCapabilities:
    """Declares what features this channel adapter supports."""

    def __init__(
        self,
        supports_streaming: bool = False,
        supports_threading: bool = True,
        supports_rich_formatting: bool = False,
        supports_interactive_elements: bool = False,
        supports_reactions: bool = False,
        supports_message_editing: bool = False,
        supports_attachments: bool = False,
        preferred_message_style: MessageStyle = MessageStyle.CONVERSATIONAL,
        max_message_length: int | None = None,
    ):
        self.supports_streaming = supports_streaming
        self.supports_threading = supports_threading
        self.supports_rich_formatting = supports_rich_formatting
        self.supports_interactive_elements = supports_interactive_elements
        self.supports_reactions = supports_reactions
        self.supports_message_editing = supports_message_editing
        self.supports_attachments = supports_attachments
        self.preferred_message_style = preferred_message_style
        self.max_message_length = max_message_length


class ChannelAdapter(ABC):
    """Base class for all channel adapters. Minimal required interface."""

    @property
    @abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """Declare what this adapter can do."""
        pass

    # RECEIVING
    @abstractmethod
    async def receive_message(self, event: dict) -> ReceivedMessage:
        """Parse incoming event and extract message content.

        Args:
            event: Raw event data from the channel

        Returns:
            ReceivedMessage with:
            - content: The actual message text
            - sender_id: User identifier in this channel
            - conversation_id: ID to link back to conversation thread
            - thread_id: Channel-specific thread/conversation ID
            - metadata: Channel-specific data (attachments, reactions, etc.)
        """
        pass

    @abstractmethod
    async def verify_request(self, request: dict) -> bool:
        """Verify request authenticity (e.g., Slack signature verification).

        Args:
            request: Request data to verify

        Returns:
            True if request is authentic, False otherwise
        """
        pass

    # SENDING (basic)
    @abstractmethod
    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send plain text message to this channel.

        Args:
            message: Plain text message to send
            conversation_id: Associated conversation ID
            thread_id: Optional channel-specific thread ID
            metadata: Optional channel-specific metadata

        Returns:
            message_id: ID for message in this channel (for threading)
        """
        pass

    # LINKING
    @abstractmethod
    async def store_conversation_mapping(
        self,
        conversation_id: UUID,
        thread_id: str,
        metadata: dict,
    ) -> None:
        """Store mapping between our conversation ID and channel's thread ID.

        Args:
            conversation_id: Our internal conversation ID
            thread_id: Channel's thread/conversation ID
            metadata: Channel-specific metadata for the mapping
        """
        pass

    @abstractmethod
    async def get_conversation_mapping(self, thread_id: str) -> UUID | None:
        """Look up our conversation ID by channel thread ID.

        Args:
            thread_id: Channel's thread ID

        Returns:
            Our internal conversation ID, or None if not found
        """
        pass


class StreamingCapable:
    """Adapters that support real-time message updates."""

    async def stream_message_chunk(
        self,
        chunk: str,
        conversation_id: UUID,
        message_id: str,
    ) -> None:
        """Stream response chunks. Can update existing message or append.

        Args:
            chunk: Text chunk to stream
            conversation_id: Associated conversation ID
            message_id: ID of message being streamed
        """
        ...


class RichFormattingCapable:
    """Adapters that support structured/rich content beyond plain text."""

    async def send_rich_message(
        self,
        content: RichMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with rich formatting (blocks, HTML, etc.).

        Args:
            content: RichMessage with formatting
            conversation_id: Associated conversation ID
            thread_id: Optional channel-specific thread ID
            metadata: Optional channel-specific metadata

        Returns:
            message_id: ID for message in this channel
        """
        ...


class InteractiveCapable:
    """Adapters that support buttons, forms, menus, etc."""

    async def send_interactive_message(
        self,
        content: InteractiveMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with interactive elements.

        Args:
            content: InteractiveMessage with buttons/forms
            conversation_id: Associated conversation ID
            thread_id: Optional channel-specific thread ID
            metadata: Optional channel-specific metadata

        Returns:
            message_id: ID for message in this channel
        """
        ...

    async def handle_interaction(self, interaction_event: dict) -> InteractionResponse:
        """Handle user interaction (button click, menu selection, etc.).

        Args:
            interaction_event: Raw interaction event from the channel

        Returns:
            InteractionResponse with action details
        """
        ...


class ReactionCapable:
    """Adapters that support reactions/emoji responses."""

    async def add_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> None:
        """Add reaction to a message (for acknowledgment, status, etc.).

        Args:
            message_id: ID of message to react to
            reaction: Reaction name/emoji
        """
        ...

    async def remove_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove reaction from a message.

        Args:
            message_id: ID of message to remove reaction from
            reaction: Reaction name/emoji to remove
        """
        ...
