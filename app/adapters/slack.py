"""Slack channel adapter implementation."""

import hashlib
import hmac
import logging
import time
from uuid import UUID

from app.adapters.base import (
    AdapterCapabilities,
    ChannelAdapter,
    InteractiveCapable,
    MessageStyle,
    ReactionCapable,
    RichFormattingCapable,
    StreamingCapable,
)
from app.adapters.models import (
    InteractionResponse,
    InteractiveMessage,
    ReceivedMessage,
    RichMessage,
)

logger = logging.getLogger(__name__)


class SlackChannelAdapter(
    ChannelAdapter, StreamingCapable, RichFormattingCapable, InteractiveCapable, ReactionCapable
):
    """Full-featured Slack adapter implementing all optional capabilities."""

    def __init__(self, bot_token: str, signing_secret: str):
        """Initialize Slack adapter.

        Args:
            bot_token: Slack bot token for API calls
            signing_secret: Slack signing secret for request verification
        """
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self._streaming_messages: dict[str, str] = {}  # Track message_id for updates

        # Note: In a real implementation, you would initialize the Slack client here
        # from slack_sdk.web.async_client import AsyncWebClient
        # self.client = AsyncWebClient(token=bot_token)

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Declare Slack's capabilities."""
        return AdapterCapabilities(
            supports_streaming=True,
            supports_threading=True,
            supports_rich_formatting=True,
            supports_interactive_elements=True,
            supports_reactions=True,
            supports_message_editing=True,
            supports_attachments=True,
            preferred_message_style=MessageStyle.CONVERSATIONAL,
            max_message_length=4000,  # Slack's text limit
        )

    async def receive_message(self, event: dict) -> ReceivedMessage:
        """Handle Slack event (message, app_mention, etc.).

        Args:
            event: Raw Slack event payload

        Returns:
            ReceivedMessage with parsed content and metadata
        """
        if event.get("type") != "event_callback":
            raise ValueError(f"Unexpected event type: {event.get('type')}")

        event_data = event.get("event", {})

        # Handle app_mention events
        if event_data.get("type") == "app_mention":
            return self._parse_app_mention(event_data)

        # Handle message events
        elif event_data.get("type") == "message":
            return self._parse_message(event_data)

        else:
            raise ValueError(f"Unsupported event type: {event_data.get('type')}")

    async def verify_request(self, request: dict) -> bool:
        """Verify Slack request signature.

        Args:
            request: Raw request data including headers

        Returns:
            True if signature is valid, False otherwise
        """
        # Slack includes these headers for signature verification
        slack_signature = request.get("headers", {}).get("X-Slack-Request-Signature", "")
        slack_timestamp = request.get("headers", {}).get("X-Slack-Request-Timestamp", "")

        # Verify timestamp is not too old (prevent replay attacks)
        try:
            request_time = int(slack_timestamp)
            if abs(time.time() - request_time) > 300:  # 5 minute window
                logger.warning("Request timestamp too old, possible replay attack")
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp format")
            return False

        # Reconstruct signing secret
        body = request.get("body", "")
        if isinstance(body, dict):
            # If body is already parsed, reconstruct raw format
            import json

            body = json.dumps(body)

        sig_basestring = f"v0:{slack_timestamp}:{body}"

        # Calculate expected signature
        my_signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
            ).hexdigest()
        )

        # Compare signatures
        return hmac.compare_digest(my_signature, slack_signature)

    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send plain text message to Slack.

        Args:
            message: Plain text message
            conversation_id: Associated conversation ID
            thread_id: Optional Slack thread timestamp
            metadata: Optional Slack-specific metadata (channel, ts, etc.)

        Returns:
            Message timestamp (ts) for reference
        """
        if not metadata:
            raise ValueError("Slack metadata required (channel, ts, etc.)")

        # In a real implementation:
        # response = await self.client.chat_postMessage(
        #     channel=metadata["channel"],
        #     text=message,
        #     thread_ts=thread_id or metadata.get("ts"),
        # )
        # return response["ts"]

        # For now, return a mock message ID
        logger.info(f"Would send to Slack: {message}")
        return f"mock_ts_{int(time.time())}"

    async def stream_message_chunk(
        self,
        chunk: str,
        conversation_id: UUID,
        message_id: str,
    ) -> None:
        """Stream response chunks by updating message.

        Args:
            chunk: Text chunk to add
            conversation_id: Associated conversation ID
            message_id: ID of message being updated
        """
        # Accumulate chunks
        if message_id not in self._streaming_messages:
            self._streaming_messages[message_id] = chunk
        else:
            self._streaming_messages[message_id] += chunk

        # In a real implementation:
        # await self.client.chat_update(
        #     channel=self._get_channel_for_message(message_id),
        #     ts=message_id,
        #     text=self._streaming_messages[message_id],
        # )

        logger.info(f"Streaming chunk to Slack: {chunk[:50]}...")

    async def send_rich_message(
        self,
        content: RichMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with Slack Block Kit formatting.

        Args:
            content: RichMessage with formatting
            conversation_id: Associated conversation ID
            thread_id: Optional Slack thread timestamp
            metadata: Optional Slack-specific metadata

        Returns:
            Message timestamp (ts)
        """
        if not metadata:
            raise ValueError("Slack metadata required")

        blocks = self._convert_to_blocks(content)

        # In a real implementation:
        # response = await self.client.chat_postMessage(
        #     channel=metadata["channel"],
        #     text=content.fallback_text,
        #     blocks=blocks,
        #     thread_ts=thread_id,
        # )
        # return response["ts"]

        logger.info(f"Would send rich message to Slack with {len(blocks)} blocks")
        return f"mock_ts_{int(time.time())}"

    async def send_interactive_message(
        self,
        content: InteractiveMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with buttons/actions.

        Args:
            content: InteractiveMessage with buttons
            conversation_id: Associated conversation ID
            thread_id: Optional Slack thread timestamp
            metadata: Optional Slack-specific metadata

        Returns:
            Message timestamp (ts)
        """
        if not metadata:
            raise ValueError("Slack metadata required")

        # In a real implementation:
        # blocks = [
        #     {
        #         "type": "section",
        #         "text": {"type": "mrkdwn", "text": content.text},
        #     },
        #     {
        #         "type": "actions",
        #         "elements": [
        #             {
        #                 "type": "button",
        #                 "text": {"type": "plain_text", "text": btn.get("label", "")},
        #                 "action_id": btn.get("action_id", ""),
        #                 "value": btn.get("value", ""),
        #             }
        #             for btn in content.buttons
        #         ],
        #     },
        # ]
        # response = await self.client.chat_postMessage(
        #     channel=metadata["channel"],
        #     text=content.text,
        #     blocks=blocks,
        #     thread_ts=thread_id,
        # )
        # return response["ts"]

        logger.info(f"Would send interactive message to Slack with {len(content.buttons)} buttons")
        return f"mock_ts_{int(time.time())}"

    async def handle_interaction(self, interaction_event: dict) -> InteractionResponse:
        """Handle button clicks, menu selections, etc.

        Args:
            interaction_event: Raw interaction event from Slack

        Returns:
            InteractionResponse with action details
        """
        actions = interaction_event.get("actions", [])
        if not actions:
            raise ValueError("No actions in interaction event")

        action = actions[0]

        return InteractionResponse(
            conversation_id=self._extract_conversation_id(interaction_event),
            action_id=action.get("action_id", ""),
            value=action.get("value", ""),
            user_id=interaction_event.get("user", {}).get("id", ""),
        )

    async def add_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> None:
        """Add emoji reaction to a message.

        Args:
            message_id: Slack message timestamp
            reaction: Emoji name (without colons)
        """
        # In a real implementation:
        # await self.client.reactions_add(
        #     channel=self._get_channel_for_message(message_id),
        #     timestamp=message_id,
        #     name=reaction,
        # )

        logger.info(f"Would add reaction :{reaction}: to message {message_id}")

    async def remove_reaction(
        self,
        message_id: str,
        reaction: str,
    ) -> None:
        """Remove emoji reaction from a message.

        Args:
            message_id: Slack message timestamp
            reaction: Emoji name (without colons)
        """
        # In a real implementation:
        # await self.client.reactions_remove(
        #     channel=self._get_channel_for_message(message_id),
        #     timestamp=message_id,
        #     name=reaction,
        # )

        logger.info(f"Would remove reaction :{reaction}: from message {message_id}")

    # Helper methods
    def _parse_app_mention(self, event_data: dict) -> ReceivedMessage:
        """Parse app_mention event."""
        return ReceivedMessage(
            content=event_data.get("text", "").replace("<@BOT_ID>", "").strip(),
            sender_id=event_data.get("user", ""),
            conversation_id=None,  # Will be looked up or created
            thread_id=event_data.get("thread_ts", event_data.get("ts", "")),
            metadata={
                "channel": event_data.get("channel", ""),
                "ts": event_data.get("ts", ""),
                "thread_ts": event_data.get("thread_ts"),
                "event_type": "app_mention",
            },
        )

    def _parse_message(self, event_data: dict) -> ReceivedMessage:
        """Parse message event."""
        return ReceivedMessage(
            content=event_data.get("text", ""),
            sender_id=event_data.get("user", ""),
            conversation_id=None,
            thread_id=event_data.get("thread_ts", event_data.get("ts", "")),
            metadata={
                "channel": event_data.get("channel", ""),
                "ts": event_data.get("ts", ""),
                "thread_ts": event_data.get("thread_ts"),
                "event_type": "message",
            },
        )

    def _convert_to_blocks(self, content: RichMessage) -> list[dict]:
        """Convert RichMessage to Slack Block Kit format."""
        # Simple conversion - in reality, this would be more sophisticated
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": content.text},
            }
        ]
        return blocks

    def _extract_conversation_id(self, interaction_event: dict) -> UUID:
        """Extract conversation ID from interaction event.

        In a real implementation, this would look up the conversation ID
        from the thread_ts stored in metadata.
        """
        # For now, return a placeholder
        from uuid import uuid4

        return uuid4()

    def _get_channel_for_message(self, message_id: str) -> str | None:
        """Get channel ID for a message (used when updating)."""
        # In a real implementation, maintain a mapping of message_id -> channel
        return None
