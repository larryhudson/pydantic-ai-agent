"""Service for executing Pydantic AI agents."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import (
    AdapterCapabilities,
    ChannelAdapter,
    MessageStyle,
    ReactionCapable,
    StreamingCapable,
)
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

    async def execute_with_channel_context(
        self,
        conversation_id: UUID,
        user_message: str,
        adapter: ChannelAdapter,
        thread_id: str | None = None,
        adapter_metadata: dict | None = None,
    ) -> str:
        """Execute agent with channel-specific adaptations.

        This method adapts agent behavior based on the channel adapter's capabilities
        (streaming, rich formatting, interaction style, etc.).

        Args:
            conversation_id: Conversation identifier
            user_message: User's message
            adapter: ChannelAdapter instance for sending responses
            thread_id: Optional channel-specific thread ID
            adapter_metadata: Optional channel-specific metadata

        Returns:
            Final agent response
        """
        caps = adapter.capabilities

        # Build channel-aware system prompt
        system_prompt = self._build_system_prompt_for_channel(caps)

        # Add user message to conversation
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.USER, user_message, db_session=self.db
        )

        # Get conversation history
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to agent format
        message_history = self._convert_messages_to_agent_format(messages)

        # Execute agent
        full_response = ""

        if caps.supports_streaming and isinstance(adapter, StreamingCapable):
            # Handle streaming response
            message_id = None

            # Add acknowledgment reaction if supported
            if isinstance(adapter, ReactionCapable):
                # Note: We'll get the message_id after first send
                pass

            async with self.agent.run_stream(
                user_message,
                message_history=message_history,
                system_prompt=system_prompt,
            ) as response:
                async for chunk in response.stream_text():
                    full_response += chunk

                    # Send first chunk to establish message
                    if message_id is None:
                        message_id = await adapter.send_message(
                            chunk,
                            conversation_id,
                            thread_id=thread_id,
                            metadata=adapter_metadata,
                        )
                    else:
                        # Stream subsequent chunks
                        await adapter.stream_message_chunk(chunk, conversation_id, message_id)

            # Mark complete
            if isinstance(adapter, ReactionCapable) and message_id:
                await adapter.add_reaction(message_id, "white_check_mark")
        else:
            # Handle complete message (no streaming)
            result = await self.agent.run(
                user_message,
                message_history=message_history,
                system_prompt=system_prompt,
            )
            full_response = str(result.data) if hasattr(result, "data") else str(result)

            await adapter.send_message(
                full_response,
                conversation_id,
                thread_id=thread_id,
                metadata=adapter_metadata,
            )

        # Save assistant response to conversation
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, full_response, db_session=self.db
        )

        return full_response

    def _build_system_prompt_for_channel(self, capabilities: AdapterCapabilities) -> str:
        """Build channel-aware system prompt based on adapter capabilities.

        Args:
            capabilities: AdapterCapabilities instance

        Returns:
            System prompt string tailored to the channel
        """
        base_prompt = "You are a helpful AI assistant."

        # Adapt for interaction style
        if capabilities.preferred_message_style == MessageStyle.CONVERSATIONAL:
            base_prompt += (
                "\n\nChannel Context: You are communicating via a real-time "
                "messaging platform (like Slack).\n\n"
                "Guidelines:\n"
                "- Keep responses concise and conversational\n"
                "- Ask clarifying questions ONE at a time (user can respond quickly)\n"
                "- Use short paragraphs and bullet points\n"
                "- Expect quick back-and-forth dialogue\n"
                "- Don't overwhelm with too much information at once"
            )
        elif capabilities.preferred_message_style == MessageStyle.COMPREHENSIVE:
            base_prompt += (
                "\n\nChannel Context: You are communicating via email or another "
                "asynchronous channel.\n\n"
                "Guidelines:\n"
                "- Write comprehensive, detailed responses\n"
                "- Anticipate follow-up questions and address them proactively\n"
                "- If you need information, ask ALL clarifying questions in one message\n"
                "- Structure responses with clear sections and headings\n"
                "- Include context and explanations - user may not reply immediately\n"
                "- Be thorough rather than brief"
            )

        # Note formatting capabilities
        if capabilities.supports_rich_formatting:
            base_prompt += "\n- You can use rich formatting (markdown, HTML, etc.)"

        if capabilities.supports_interactive_elements:
            base_prompt += "\n- You can suggest interactive elements (buttons, forms)"

        return base_prompt

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
