"""API endpoints for conversation management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import create_agent_runner
from app.database import get_db
from app.models.domain import (
    ConversationThread,
    CreateConversationRequest,
    Message,
    SendMessageRequest,
)
from app.services.agent_executor import AgentExecutor
from app.services.conversation_manager import ConversationManager

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationThread)
async def create_conversation(
    request: CreateConversationRequest,
    user_id: str = "default_user",  # In production, get from auth
    db: AsyncSession = Depends(get_db),
) -> ConversationThread:
    """Create a new conversation thread.

    Args:
        request: Conversation creation request
        user_id: User identifier (from authentication)
        db: Database session

    Returns:
        Created conversation thread
    """
    manager = ConversationManager(db)
    conversation = await manager.create_conversation(
        user_id=user_id,
        pattern_type=request.pattern_type,
        context_data=request.context_data,
    )
    return conversation


@router.get("/{conversation_id}", response_model=ConversationThread)
async def get_conversation(
    conversation_id: UUID,
    load_messages: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ConversationThread:
    """Get a conversation by ID.

    Args:
        conversation_id: Conversation identifier
        load_messages: Whether to load message history
        db: Database session

    Returns:
        Conversation thread

    Raises:
        HTTPException: If conversation not found
    """
    manager = ConversationManager(db)
    conversation = await manager.get_conversation(conversation_id, load_messages=load_messages)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.get("/{conversation_id}/messages", response_model=list[Message])
async def get_messages(
    conversation_id: UUID,
    limit: int | None = None,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    """Get messages for a conversation.

    Args:
        conversation_id: Conversation identifier
        limit: Optional limit on number of messages
        offset: Offset for pagination
        db: Database session

    Returns:
        List of messages
    """
    manager = ConversationManager(db)
    messages = await manager.get_messages(conversation_id, limit=limit, offset=offset)
    return messages


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and get agent response.

    Args:
        conversation_id: Conversation identifier
        request: Message request
        db: Database session

    Returns:
        Agent response (streaming if requested, otherwise JSON)
    """
    manager = ConversationManager(db)

    # Check if conversation exists
    conversation = await manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Create runner and executor
    runner = create_agent_runner()
    executor = AgentExecutor(runner, manager)

    if request.stream:
        # Streaming response

        async def generate():
            async for chunk in executor.execute_sync(
                conversation_id=conversation_id,
                user_message=request.message,
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/plain")
    else:
        # Non-streaming response
        response_text = ""
        async for chunk in executor.execute_sync(
            conversation_id=conversation_id,
            user_message=request.message,
        ):
            response_text += chunk

        return {"message": response_text}


@router.post("/{conversation_id}/continue", response_model=ConversationThread)
async def continue_conversation(
    conversation_id: UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationThread:
    """Continue a conversation with a follow-up message.

    Args:
        conversation_id: Conversation identifier
        request: Message request
        db: Database session

    Returns:
        Updated conversation thread

    Raises:
        HTTPException: If conversation not found
    """
    manager = ConversationManager(db)

    try:
        conversation = await manager.continue_thread(conversation_id, request.message)
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
