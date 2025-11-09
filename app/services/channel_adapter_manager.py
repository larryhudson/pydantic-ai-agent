"""Manager for channel adapters and message routing."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ChannelAdapter
from app.database.models import ConversationChannelAdapterDB
from app.models.domain import ConversationChannelAdapter, MessageRole
from app.services.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)

# Global adapter registry
_global_adapters: dict[str, ChannelAdapter] = {}


class SecurityError(Exception):
    """Raised when request signature verification fails."""

    pass


class ChannelAdapterManager:
    """Manages channel adapter registration and message routing."""

    def __init__(self, db_session: AsyncSession | None = None):
        self.db_session = db_session
        # Use global adapters registry
        self._adapters = _global_adapters

    async def register_adapter(self, name: str, adapter: ChannelAdapter) -> None:
        """Register a new channel adapter.

        Args:
            name: Adapter name (e.g., "slack", "email", "github")
            adapter: ChannelAdapter instance
        """
        self._adapters[name] = adapter

    def get_adapter(self, name: str) -> ChannelAdapter:
        """Get a registered adapter by name.

        Args:
            name: Adapter name

        Returns:
            ChannelAdapter instance

        Raises:
            KeyError: If adapter not found
        """
        return self._adapters[name]

    def list_adapters(self) -> list[str]:
        """Get list of registered adapter names.

        Returns:
            List of adapter names
        """
        return list(self._adapters.keys())

    async def handle_incoming_event(
        self,
        adapter_name: str,
        event_data: dict,
        conversation_manager: ConversationManager,
        db_session: AsyncSession,
    ) -> tuple[UUID, str]:
        """Route incoming message from adapter to conversation.

        Args:
            adapter_name: Name of the adapter receiving the message
            event_data: Raw event data from the adapter
            conversation_manager: ConversationManager instance
            db_session: Database session for persistence

        Returns:
            Tuple of (conversation_id, thread_id)
        """
        adapter = self.get_adapter(adapter_name)

        # Parse message via adapter
        # Note: request signature verification is done at the endpoint level
        logger.info(f"Parsing message from adapter {adapter_name}")
        message = await adapter.receive_message(event_data)
        logger.info(f"Parsed message: content={message.content[:50]}, thread_id={message.thread_id}, metadata={message.metadata}")

        # 3. Look up or create conversation
        conversation_id = await self._get_conversation_mapping(
            adapter_name, message.thread_id, db_session
        )
        logger.info(f"Conversation mapping lookup result: {conversation_id}")

        if conversation_id is None:
            # Create new conversation
            logger.info(f"Creating new conversation for {adapter_name}")
            conversation = await conversation_manager.create_conversation(
                user_id=message.sender_id,
                pattern_type="channel_adapter",
                context_data={
                    "adapter_name": adapter_name,
                    "initial_thread_id": message.thread_id,
                },
            )
            conversation_id = conversation.id
            logger.info(f"Created conversation {conversation_id}")

            # Store adapter mapping
            logger.info(f"Storing mapping with metadata: {message.metadata}")
            await self._store_conversation_mapping(
                conversation_id=conversation_id,
                adapter_name=adapter_name,
                thread_id=message.thread_id,
                metadata=message.metadata,
                db_session=db_session,
            )

        # 4. Add message to conversation
        await conversation_manager.add_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=message.content,
            adapter_name=adapter_name,
            adapter_message_id=message.thread_id,
        )

        return conversation_id, message.thread_id

    async def send_to_adapter(
        self,
        conversation_id: UUID,
        message: str,
        adapter_name: str,
        db_session: AsyncSession,
    ) -> None:
        """Send message to conversation's channel adapter.

        Args:
            conversation_id: Conversation to send to
            message: Message content
            adapter_name: Name of adapter to send via
            db_session: Database session
        """
        adapter = self.get_adapter(adapter_name)

        # Get adapter mapping for this conversation
        mapping = await self._get_adapter_mapping(conversation_id, adapter_name, db_session)

        if mapping is None:
            raise ValueError(
                f"No adapter mapping for conversation {conversation_id} and adapter {adapter_name}"
            )

        # Send via adapter
        await adapter.send_message(
            message=message,
            conversation_id=conversation_id,
            thread_id=mapping.thread_id,
            metadata=mapping.adapter_metadata,
        )

    async def _store_conversation_mapping(
        self,
        conversation_id: UUID,
        adapter_name: str,
        thread_id: str,
        metadata: dict,
        db_session: AsyncSession,
    ) -> None:
        """Store mapping between conversation and adapter thread.

        Args:
            conversation_id: Our conversation ID
            adapter_name: Adapter name
            thread_id: Adapter's thread ID
            metadata: Channel-specific metadata
            db_session: Database session
        """
        logger.info(f"Storing adapter mapping: adapter={adapter_name}, thread_id={thread_id}, metadata={metadata}")
        db_mapping = ConversationChannelAdapterDB(
            conversation_id=conversation_id,
            adapter_name=adapter_name,
            thread_id=thread_id,
            adapter_metadata=metadata,
        )
        logger.info(f"Created db_mapping with metadata: {db_mapping.adapter_metadata}")
        db_session.add(db_mapping)
        await db_session.flush()
        logger.info(f"After flush, db_mapping.adapter_metadata: {db_mapping.adapter_metadata}")

    async def _get_conversation_mapping(
        self, adapter_name: str, thread_id: str, db_session: AsyncSession
    ) -> UUID | None:
        """Look up conversation ID by adapter name and thread ID.

        Args:
            adapter_name: Adapter name
            thread_id: Adapter's thread ID
            db_session: Database session

        Returns:
            Conversation ID, or None if not found
        """
        from sqlalchemy import select

        stmt = select(ConversationChannelAdapterDB.conversation_id).where(
            (ConversationChannelAdapterDB.adapter_name == adapter_name)
            & (ConversationChannelAdapterDB.thread_id == thread_id)
        )
        result = await db_session.execute(stmt)
        return result.scalars().first()

    async def _get_adapter_mapping(
        self,
        conversation_id: UUID,
        adapter_name: str,
        db_session: AsyncSession,
    ) -> ConversationChannelAdapter | None:
        """Get adapter mapping for a conversation.

        Args:
            conversation_id: Conversation ID
            adapter_name: Adapter name
            db_session: Database session

        Returns:
            ConversationChannelAdapter, or None if not found
        """
        from sqlalchemy import select

        stmt = select(ConversationChannelAdapterDB).where(
            (ConversationChannelAdapterDB.conversation_id == conversation_id)
            & (ConversationChannelAdapterDB.adapter_name == adapter_name)
        )
        result = await db_session.execute(stmt)
        db_mapping = result.scalars().first()

        if db_mapping is None:
            return None

        return ConversationChannelAdapter(
            id=db_mapping.id,
            conversation_id=db_mapping.conversation_id,
            adapter_name=db_mapping.adapter_name,
            thread_id=db_mapping.thread_id,
            adapter_metadata=db_mapping.adapter_metadata,
            created_at=db_mapping.created_at,
        )


async def initialize_adapters() -> None:
    """Initialize and register all configured channel adapters.

    This function instantiates adapters based on environment configuration
    and registers them globally. It should be called during application startup
    and can be called again in worker processes.
    """
    from app.config import get_settings

    settings = get_settings()
    manager = ChannelAdapterManager()

    # Initialize Slack adapter if configured
    if settings.slack_bot_token and settings.slack_signing_secret:
        from app.adapters.slack import SlackChannelAdapter

        slack_adapter = SlackChannelAdapter(
            bot_token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret,
        )
        await manager.register_adapter("slack", slack_adapter)
        logger.info("Slack adapter initialized")
    else:
        logger.debug("Slack adapter not configured (missing credentials)")

    # Initialize Email adapter if configured
    if settings.mailgun_api_key and settings.mailgun_domain:
        from app.adapters.email import EmailChannelAdapter

        email_adapter = EmailChannelAdapter(
            mailgun_api_key=settings.mailgun_api_key,
            mailgun_domain=settings.mailgun_domain,
        )
        await manager.register_adapter("email", email_adapter)
        logger.info("Email adapter (Mailgun) initialized")
    else:
        logger.debug("Email adapter not configured (missing credentials)")
