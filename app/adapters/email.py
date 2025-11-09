"""Email channel adapter implementation using Mailgun."""

import hashlib
import hmac
import logging
import time
from uuid import UUID

import aiohttp

from app.adapters.base import AdapterCapabilities, ChannelAdapter, MessageStyle
from app.adapters.models import ReceivedMessage
from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailChannelAdapter(ChannelAdapter):
    """Email adapter using Mailgun for sending and receiving.

    No streaming, no interactivity, but comprehensive message style.
    Handles both sending via Mailgun API and receiving via webhooks.
    """

    def __init__(self, mailgun_api_key: str, mailgun_domain: str):
        """Initialize email adapter with Mailgun credentials.

        Args:
            mailgun_api_key: Mailgun API key for authentication
            mailgun_domain: Mailgun domain for sending emails
        """
        self.mailgun_api_key = mailgun_api_key
        self.mailgun_domain = mailgun_domain
        self.mailgun_api_url = f"https://api.mailgun.net/v3/{mailgun_domain}"
        settings = get_settings()
        self.from_email = settings.mailgun_from_email

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Declare email's limited capabilities compared to Slack."""
        return AdapterCapabilities(
            supports_streaming=False,  # Can't edit sent emails
            supports_threading=True,  # Via In-Reply-To/References headers
            supports_rich_formatting=True,  # HTML emails supported
            supports_interactive_elements=False,  # No buttons/forms in email
            supports_reactions=False,  # No emoji reactions
            supports_message_editing=False,  # Can't unsend emails
            supports_attachments=True,  # Email supports attachments
            preferred_message_style=MessageStyle.COMPREHENSIVE,  # Detailed messages
            max_message_length=None,  # No hard limit
        )

    async def receive_message(self, mailgun_event: dict) -> ReceivedMessage:
        """Parse Mailgun incoming email webhook and extract message.

        Args:
            mailgun_event: Mailgun event data from webhook

        Returns:
            ReceivedMessage with parsed email content
        """
        # Extract message ID for threading
        message_id = mailgun_event.get("message-id", "")

        # Extract the email body - prefer plain text, fall back to HTML
        body_plain = mailgun_event.get("body-plain", "")
        body_html = mailgun_event.get("body-html", "")
        content = body_plain if body_plain else body_html

        # Extract In-Reply-To for conversation threading
        in_reply_to = mailgun_event.get("In-Reply-To")

        return ReceivedMessage(
            content=content,
            sender_id=mailgun_event.get("sender", ""),
            conversation_id=None,  # Mapped via thread_id/In-Reply-To
            thread_id=in_reply_to or message_id,  # Use In-Reply-To if available for threading
            metadata={
                "message_id": message_id,
                "in_reply_to": in_reply_to,
                "subject": mailgun_event.get("subject", ""),
                "from_addr": mailgun_event.get("from", ""),
                "to_addr": mailgun_event.get("recipient", ""),
                "cc": mailgun_event.get("Cc", "").split(",") if mailgun_event.get("Cc") else [],
                "attachments": mailgun_event.get("attachments", []),
            },
        )

    async def verify_request(self, request_data: dict) -> bool:
        """Verify Mailgun webhook signature.

        Args:
            request_data: Request data containing signature and token/timestamp

        Returns:
            True if signature is valid, False otherwise
        """
        # Mailgun provides three pieces of data for signature verification:
        # - timestamp: Unix timestamp
        # - token: Random alphanumeric string
        # - signature: HMAC SHA256 of "{timestamp}{token}"
        timestamp = request_data.get("timestamp")
        token = request_data.get("token")
        signature = request_data.get("signature")

        if not all([timestamp, token, signature]):
            logger.warning("Missing signature components")
            return False

        # Verify timestamp isn't too old (Mailgun default is 15 minutes)
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())
            if current_time - timestamp_int > 900:  # 15 minutes
                logger.warning("Timestamp too old")
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp")
            return False

        # Compute the expected signature
        msg = f"{timestamp}{token}".encode()
        expected_signature = hmac.new(
            self.mailgun_api_key.encode(),
            msg,
            hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)

    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send comprehensive response via Mailgun API.

        Args:
            message: Message content (agent will generate comprehensive message)
            conversation_id: Associated conversation ID
            thread_id: Optional In-Reply-To message ID for threading
            metadata: Email metadata (from_addr, subject, etc.)

        Returns:
            Message ID (for reference)

        Raises:
            ValueError: If required metadata is missing
        """
        if not metadata:
            raise ValueError("Email metadata required (from_addr, subject, etc.)")

        recipient = metadata.get("from_addr")
        if not recipient:
            raise ValueError("from_addr required in metadata")

        subject = metadata.get("subject", "Agent Response")
        if metadata.get("in_reply_to"):
            # For replies, prefix subject with "Re:"
            if not subject.startswith("Re:"):
                subject = f"Re: {subject}"

        # Prepare email data for Mailgun API
        email_data = {
            "from": self.from_email,
            "to": recipient,
            "subject": subject,
            "text": message,
        }

        # Add threading headers if this is a reply
        if thread_id:
            email_data["h:In-Reply-To"] = thread_id

        # Send via Mailgun REST API
        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth("api", self.mailgun_api_key)
            try:
                async with session.post(
                    f"{self.mailgun_api_url}/messages",
                    data=email_data,
                    auth=auth,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        message_id = result.get("id", "")
                        logger.info(f"Email sent to {recipient}: {message_id}")
                        return message_id
                    else:
                        error_text = await resp.text()
                        logger.error(
                            f"Failed to send email via Mailgun: {resp.status} {error_text}"
                        )
                        raise RuntimeError(f"Mailgun API error: {resp.status}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error sending email via Mailgun: {e}")
                raise RuntimeError(f"Failed to contact Mailgun: {e}") from e

    async def get_new_messages(self) -> list[ReceivedMessage]:
        """Mailgun uses webhooks for incoming emails, no polling needed.

        With Mailgun's webhook integration, incoming emails are delivered
        immediately to our webhook endpoint. This method is kept for
        compatibility with the base interface but is not used.

        Returns:
            Empty list (messages arrive via webhook)
        """
        logger.debug("Mailgun adapter uses webhooks for incoming emails - no polling needed")
        return []

    async def store_conversation_mapping(
        self,
        conversation_id: UUID,
        thread_id: str,
        metadata: dict,
    ) -> None:
        """Store mapping between conversation and email thread ID.

        This is handled by the ChannelAdapterManager which persists
        ConversationChannelAdapterDB entries.

        Args:
            conversation_id: Our internal conversation ID
            thread_id: Email's Message-ID for threading
            metadata: Additional metadata for the mapping
        """
        # Implementation delegated to ChannelAdapterManager.handle_incoming_event()
        # which creates ConversationChannelAdapterDB entries
        logger.debug(f"Storing mapping: conversation {conversation_id} -> thread {thread_id}")

    async def get_conversation_mapping(self, thread_id: str) -> UUID | None:
        """Look up conversation ID by email thread ID.

        This is handled by the ChannelAdapterManager which queries
        ConversationChannelAdapterDB.

        Args:
            thread_id: Email's Message-ID or In-Reply-To

        Returns:
            Our internal conversation ID, or None if not found
        """
        # Implementation delegated to ChannelAdapterManager.handle_incoming_event()
        # which queries ConversationChannelAdapterDB
        logger.debug(f"Looking up conversation for thread {thread_id}")
        return None
