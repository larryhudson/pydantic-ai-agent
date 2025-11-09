"""Service for executing agents with conversation context."""

from collections.abc import AsyncIterator
from typing import Any, cast
from uuid import UUID

from app.adapters.base import (
    AdapterCapabilities,
    ChannelAdapter,
    MessageStyle,
    ReactionCapable,
    StreamingCapable,
)
from app.models.domain import MessageRole
from app.runners.base import AgentRunner
from app.runners.models import ExecutionContext, StreamChunk
from app.runners.models import MessageRole as RunnerMessageRole
from app.services.conversation_manager import ConversationManager


class AgentExecutor:
    """Orchestrates agent execution and conversation persistence.

    Responsibilities:
    - Load conversation history from database
    - Delegate execution to runner
    - Save messages back to database
    - Handle errors and retries
    """

    def __init__(self, runner: AgentRunner, conversation_manager: ConversationManager):
        """Initialize with runner and conversation manager.

        Args:
            runner: AgentRunner instance for agent execution
            conversation_manager: ConversationManager for persistence
        """
        self.runner = runner
        self.conversation_manager = conversation_manager

    async def execute_sync(
        self,
        conversation_id: UUID,
        user_message: str,
    ) -> AsyncIterator[str]:
        """Execute agent with streaming, managing conversation persistence.

        This method is used for chatbot and sidekick patterns where
        the user expects an immediate streaming response.

        Args:
            conversation_id: Conversation identifier
            user_message: User's input message

        Yields:
            String chunks of the response
        """
        # Add user message to conversation
        await self.conversation_manager.add_message(conversation_id, MessageRole.USER, user_message)

        # Load message history for context
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to agent runner format
        history = [self._to_agent_message(msg) for msg in messages]

        # Execute with runner
        response_content = []
        async with self.runner.session():
            context = ExecutionContext(conversation_id=conversation_id)

            stream = cast(
                AsyncIterator[StreamChunk],
                self.runner.execute_streaming(
                    prompt=user_message,
                    message_history=history,
                    context=context,
                ),
            )
            async for chunk in stream:
                response_content.append(chunk.content)
                yield chunk.content

        # Save assistant response
        await self.conversation_manager.add_message(
            conversation_id,
            MessageRole.ASSISTANT,
            "".join(response_content),
        )

    async def execute_async(
        self,
        conversation_id: UUID,
        prompt: str,
    ) -> str:
        """Execute agent without streaming, managing conversation persistence.

        This method is used for delegation, scheduled, and triggered patterns
        where the execution happens in the background. It adds a new user message,
        executes the agent, and saves the response.

        Args:
            conversation_id: Conversation identifier
            prompt: Prompt for the agent

        Returns:
            Final agent response
        """
        # Add user message
        await self.conversation_manager.add_message(conversation_id, MessageRole.USER, prompt)

        # Load message history for context
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to agent runner format
        history = [self._to_agent_message(msg) for msg in messages]

        # Execute with runner
        async with self.runner.session():
            context = ExecutionContext(conversation_id=conversation_id)

            result = await self.runner.execute_non_streaming(
                prompt=prompt,
                message_history=history,
                context=context,
            )

        # Save assistant response
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, result.content
        )

        return result.content

    async def execute_on_existing_conversation(
        self,
        conversation_id: UUID,
    ) -> str:
        """Execute agent on an existing conversation with already-persisted messages.

        This method is used when processing messages that have already been added
        to the conversation (e.g., by channel adapters). It executes the agent
        using existing message history and saves only the assistant response.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Final agent response
        """
        # Load existing message history
        messages = await self.conversation_manager.get_messages(conversation_id)

        if not messages:
            raise ValueError(f"No messages found in conversation {conversation_id}")

        # Get the last user message as the prompt
        user_message = None
        for msg in reversed(messages):
            if msg.role == MessageRole.USER:
                user_message = msg.content
                break

        if not user_message:
            raise ValueError(f"No user message found in conversation {conversation_id}")

        # Convert to agent runner format
        history = [self._to_agent_message(msg) for msg in messages]

        # Execute with runner
        async with self.runner.session():
            context = ExecutionContext(conversation_id=conversation_id)

            result = await self.runner.execute_non_streaming(
                prompt=user_message,
                message_history=history,
                context=context,
            )

        # Save assistant response
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, result.content
        )

        return result.content

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

        # Note: Channel-aware system prompt can be built here using
        # _build_system_prompt_for_channel and passed via ExecutionContext

        # Add user message to conversation
        await self.conversation_manager.add_message(conversation_id, MessageRole.USER, user_message)

        # Get conversation history
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Convert to agent runner format
        history = [self._to_agent_message(msg) for msg in messages]

        # Execute agent
        full_response = ""
        async with self.runner.session():
            context = ExecutionContext(
                conversation_id=conversation_id,
                system_prompt=self._build_system_prompt_for_channel(caps),
            )

            if (
                caps.supports_streaming
                and self.runner.capabilities.supports_streaming
                and isinstance(adapter, StreamingCapable)
            ):
                # Handle streaming response
                message_id = None

                stream = cast(
                    AsyncIterator[StreamChunk],
                    self.runner.execute_streaming(
                        prompt=user_message,
                        message_history=history,
                        context=context,
                    ),
                )
                async for chunk in stream:
                    full_response += chunk.content

                    # Send first chunk to establish message
                    if message_id is None:
                        message_id = await adapter.send_message(
                            chunk.content,
                            conversation_id,
                            thread_id=thread_id,
                            metadata=adapter_metadata,
                        )
                    else:
                        # Stream subsequent chunks
                        await adapter.stream_message_chunk(
                            chunk.content, conversation_id, message_id
                        )

                # Mark complete
                if isinstance(adapter, ReactionCapable) and message_id:
                    await adapter.add_reaction(message_id, "white_check_mark")
            else:
                # Handle complete message (no streaming)
                result = await self.runner.execute_non_streaming(
                    prompt=user_message,
                    message_history=history,
                    context=context,
                )
                full_response = result.content

                await adapter.send_message(
                    full_response,
                    conversation_id,
                    thread_id=thread_id,
                    metadata=adapter_metadata,
                )

        # Save assistant response to conversation
        await self.conversation_manager.add_message(
            conversation_id, MessageRole.ASSISTANT, full_response
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

    def _to_agent_message(self, db_message: Any) -> Any:
        """Convert database message to AgentMessage.

        Args:
            db_message: Message from database

        Returns:
            AgentMessage for runner
        """
        from app.runners.models import AgentMessage

        return AgentMessage(
            role=RunnerMessageRole(db_message.role),
            content=db_message.content,
            tool_calls=getattr(db_message, "tool_calls", None),
        )
