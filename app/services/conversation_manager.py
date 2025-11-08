"""Service for managing conversation threads and messages."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import ConversationDB, MessageDB
from app.models.domain import ConversationThread, Message, MessageRole


class ConversationManager:
    """Manages conversation threads and message history."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def create_conversation(
        self, user_id: str, pattern_type: str, context_data: dict | None = None
    ) -> ConversationThread:
        """Create a new conversation thread.

        Args:
            user_id: User identifier
            pattern_type: Type of interaction pattern
            context_data: Optional context data for the conversation

        Returns:
            Created conversation thread
        """
        conversation_db = ConversationDB(
            user_id=user_id,
            pattern_type=pattern_type,
            context_data=context_data or {},
        )

        self.db.add(conversation_db)
        await self.db.commit()
        await self.db.refresh(conversation_db)

        return self._to_domain(conversation_db)

    async def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        tool_calls: list[dict] | None = None,
        tool_results: list[dict] | None = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation identifier
            role: Message role (user/assistant/system)
            content: Message content
            tool_calls: Optional tool calls made
            tool_results: Optional tool results

        Returns:
            Created message
        """
        message_db = MessageDB(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
        )

        self.db.add(message_db)

        # Update conversation's updated_at timestamp
        conversation_db = await self.db.get(ConversationDB, conversation_id)
        if conversation_db:
            conversation_db.updated_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(message_db)

        return self._message_to_domain(message_db)

    async def get_conversation(
        self, conversation_id: UUID, load_messages: bool = False
    ) -> ConversationThread | None:
        """Get a conversation by ID.

        Args:
            conversation_id: Conversation identifier
            load_messages: Whether to load message history

        Returns:
            Conversation thread or None if not found
        """
        query = select(ConversationDB).where(ConversationDB.id == conversation_id)

        if load_messages:
            query = query.options(selectinload(ConversationDB.messages))

        result = await self.db.execute(query)
        conversation_db = result.scalar_one_or_none()

        if not conversation_db:
            return None

        return self._to_domain(conversation_db, include_messages=load_messages)

    async def get_messages(
        self, conversation_id: UUID, limit: int | None = None, offset: int = 0
    ) -> list[Message]:
        """Retrieve message history for a conversation.

        Args:
            conversation_id: Conversation identifier
            limit: Optional limit on number of messages
            offset: Offset for pagination

        Returns:
            List of messages
        """
        query = (
            select(MessageDB)
            .where(MessageDB.conversation_id == conversation_id)
            .order_by(MessageDB.created_at)
            .offset(offset)
        )

        if limit:
            query = query.limit(limit)

        result = await self.db.execute(query)
        messages_db = result.scalars().all()

        return [self._message_to_domain(msg) for msg in messages_db]

    async def continue_thread(self, conversation_id: UUID, user_message: str) -> ConversationThread:
        """Continue an existing thread with a follow-up message.

        Args:
            conversation_id: Conversation identifier
            user_message: User's message

        Returns:
            Updated conversation thread
        """
        # Add the user message
        await self.add_message(conversation_id, MessageRole.USER, user_message)

        # Get and return the updated conversation
        conversation = await self.get_conversation(conversation_id, load_messages=True)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")

        return conversation

    async def update_context(self, conversation_id: UUID, context_data: dict) -> None:
        """Update conversation context data.

        Args:
            conversation_id: Conversation identifier
            context_data: New context data
        """
        conversation_db = await self.db.get(ConversationDB, conversation_id)
        if not conversation_db:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation_db.context_data = context_data
        conversation_db.updated_at = datetime.now(UTC)
        await self.db.commit()

    @staticmethod
    def _to_domain(
        conversation_db: ConversationDB, include_messages: bool = False
    ) -> ConversationThread:
        """Convert database model to domain model."""
        messages = []
        if include_messages and conversation_db.messages:
            messages = [
                ConversationManager._message_to_domain(msg) for msg in conversation_db.messages
            ]

        return ConversationThread(
            id=conversation_db.id,
            user_id=conversation_db.user_id,
            created_at=conversation_db.created_at,
            updated_at=conversation_db.updated_at,
            status=conversation_db.status,
            pattern_type=conversation_db.pattern_type,
            context_data=conversation_db.context_data,
            messages=messages,
            task_id=conversation_db.task_id,
        )

    @staticmethod
    def _message_to_domain(message_db: MessageDB) -> Message:
        """Convert database message to domain message."""
        return Message(
            id=message_db.id,
            conversation_id=message_db.conversation_id,
            role=message_db.role,
            content=message_db.content,
            created_at=message_db.created_at,
            tool_calls=message_db.tool_calls,
            tool_results=message_db.tool_results,
        )
