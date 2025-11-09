"""Email channel adapter implementation."""

import logging
from uuid import UUID

from app.adapters.base import AdapterCapabilities, ChannelAdapter, MessageStyle
from app.adapters.models import ReceivedMessage

logger = logging.getLogger(__name__)


class EmailChannelAdapter(ChannelAdapter):
    """Basic email adapter - only implements base interface.

    No streaming, no interactivity, but comprehensive message style.
    Designed for email communication via IMAP/SMTP.
    """

    def __init__(self, imap_config: dict, smtp_config: dict):
        """Initialize email adapter.

        Args:
            imap_config: IMAP configuration (host, username, password, etc.)
            smtp_config: SMTP configuration (host, port, username, password, etc.)
        """
        self.imap_config = imap_config
        self.smtp_config = smtp_config

        # Note: In a real implementation, you would initialize email clients:
        # import aiosmtplib
        # from aioimaplib import IMAP4_SSL
        # self.imap = IMAP4_SSL(host=imap_config["host"])
        # self.smtp = aiosmtplib.SMTP(hostname=smtp_config["host"])

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

    async def receive_message(self, email_msg: dict) -> ReceivedMessage:
        """Parse incoming email and extract message.

        Args:
            email_msg: Email message data (from IMAP or similar)

        Returns:
            ReceivedMessage with parsed email content
        """
        return ReceivedMessage(
            content=email_msg.get("body", ""),
            sender_id=email_msg.get("from_addr", ""),
            conversation_id=None,  # Mapped via In-Reply-To header
            thread_id=email_msg.get("message_id", ""),
            metadata={
                "in_reply_to": email_msg.get("in_reply_to"),
                "subject": email_msg.get("subject", ""),
                "attachments": email_msg.get("attachments", []),
                "from_addr": email_msg.get("from_addr", ""),
                "to_addr": email_msg.get("to_addr", ""),
                "cc": email_msg.get("cc", []),
                "bcc": email_msg.get("bcc", []),
            },
        )

    async def verify_request(self, request: dict) -> bool:
        """Email doesn't have webhook signatures - validate via IMAP auth.

        Args:
            request: Request data (not used for email)

        Returns:
            True (already authenticated via IMAP)
        """
        # Email is already authenticated via IMAP login
        # In a real implementation, you might validate sender address
        return True

    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send comprehensive response via SMTP.

        Args:
            message: Message content (agent will generate comprehensive message)
            conversation_id: Associated conversation ID
            thread_id: Optional In-Reply-To message ID
            metadata: Email metadata (from_addr, subject, etc.)

        Returns:
            Message ID (for reference)
        """
        if not metadata:
            raise ValueError("Email metadata required (from_addr, subject, etc.)")

        # In a real implementation:
        # from email.mime.text import MIMEText
        # from email.mime.multipart import MIMEMultipart
        #
        # email_msg = MIMEMultipart("alternative")
        # email_msg["Subject"] = f"Re: {metadata['subject']}"
        # email_msg["From"] = self.smtp_config["from_email"]
        # email_msg["To"] = metadata["from_addr"]
        # if thread_id:
        #     email_msg["In-Reply-To"] = thread_id
        # email_msg["References"] = thread_id or ""
        #
        # part1 = MIMEText(message, "plain")
        # email_msg.attach(part1)
        #
        # async with aiosmtplib.SMTP(hostname=self.smtp_config["host"]) as smtp:
        #     await smtp.send_message(email_msg)
        #
        # return email_msg.get("Message-ID")

        logger.info(f"Would send email to {metadata.get('from_addr')}: {message[:100]}...")

        # Return mock message ID
        import uuid

        return f"email_{uuid.uuid4()}"

    async def get_new_messages(self) -> list[ReceivedMessage]:
        """Poll IMAP for new messages.

        This would be called by a background job to fetch new emails.

        Returns:
            List of ReceivedMessage from unread emails
        """
        # In a real implementation:
        # await self.imap.login(self.imap_config["username"], self.imap_config["password"])
        # await self.imap.select("INBOX")
        #
        # # Fetch unread messages
        # status, message_ids = await self.imap.search(None, "UNSEEN")
        #
        # messages = []
        # for msg_id in message_ids[0].split():
        #     status, msg_data = await self.imap.fetch(msg_id, "(RFC822)")
        #     email_msg = email.message_from_bytes(msg_data[0][1])
        #     messages.append(self.receive_message(email_msg))
        #
        # return messages

        logger.info("Would poll IMAP for new messages")
        return []
