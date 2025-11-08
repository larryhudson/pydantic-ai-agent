"""Service for executing Pydantic AI agents."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain import MessageRole
from app.services.conversation_manager import ConversationManager


class AgentExecutor:
    """Executes Pydantic AI agents with conversation context."""

    def __init__(self, agent: Agent, db: AsyncSession):
        """Initialize with agent and database session.

        Args:
            agent: Pydantic AI agent to execute
            db: Database session for conversation management
        """
        self.agent = agent
        self.db = db
        self.conversation_manager = ConversationManager(db)

    async def execute_sync(
        self,
        conversation_id: UUID,
        user_message: str,
        context: dict | None = None,
    ) -> AsyncIterator[str]:
        """Execute agent synchronously with streaming.

        This method is used for chatbot and sidekick patterns where
        the user expects an immediate streaming response.

        Args:
            conversation_id: Conversation identifier
            user_message: User's input message
            context: Optional context data for the agent

        Yields:
            Chunks of the agent's response
        """
        # Add user message to conversation
        await self.conversation_manager.add_message(conversation_id, MessageRole.USER, user_message)

        # Load message history for context
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to format expected by agent (if needed)
        message_history = self._convert_messages_to_agent_format(messages)

        # Run agent with streaming
        # Note: context/deps handling will depend on agent configuration
        full_response = ""
        async with self.agent.run_stream(user_message, message_history=message_history) as response:
            async for chunk in response.stream_text():
                full_response += chunk
                yield chunk

        # Save assistant response to conversation
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, full_response
        )

    async def execute_async(
        self,
        conversation_id: UUID,
        prompt: str,
        context: dict | None = None,
    ) -> str:
        """Execute agent asynchronously, return final result.

        This method is used for delegation, scheduled, and triggered patterns
        where the execution happens in the background.

        Args:
            conversation_id: Conversation identifier
            prompt: Task prompt/instruction
            context: Optional context data for the agent

        Returns:
            Final agent response
        """
        # Add prompt as user message
        await self.conversation_manager.add_message(conversation_id, MessageRole.USER, prompt)

        # Load message history for context
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to format expected by agent
        message_history = self._convert_messages_to_agent_format(messages)

        # Run agent without streaming
        # Note: context/deps handling will depend on agent configuration
        result = await self.agent.run(prompt, message_history=message_history)

        # Save assistant response
        response_text = str(result.data) if hasattr(result, "data") else str(result)
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, response_text
        )

        return response_text

    def _convert_messages_to_agent_format(self, messages: list[Any]) -> list[ModelMessage]:
        """Convert conversation messages to Pydantic AI message format.

        Args:
            messages: Conversation messages

        Returns:
            List of messages in agent format
        """
        # For now, return empty list - in a real implementation,
        # you would convert messages to the format expected by Pydantic AI
        # This depends on the specific agent configuration
        return []


def create_default_agent(model: str = "openai:gpt-4") -> Agent:
    """Create a default agent with basic configuration.

    Args:
        model: Model identifier (e.g., "openai:gpt-4", "anthropic:claude-3-opus")

    Returns:
        Configured Pydantic AI agent
    """
    agent = Agent(
        model=model,
        system_prompt=(
            "You are a helpful AI assistant. Provide clear, concise, "
            "and accurate responses to user queries."
        ),
    )

    return agent
