# Channel Adapter Pattern for Multi-Channel Agent Communication

## Vision

Instead of treating external platforms as **notification channels** (one-way output), treat them as **channel adapters** (bidirectional). This enables agents to have conversations in the channels where users already work, rather than forcing users to jump between interfaces.

**Note:** We call these "ChannelAdapters" to distinguish from other types of adapters (e.g., data adapters, tool adapters). Channel adapters specifically handle bidirectional communication with external platforms.

**Three interaction patterns become possible:**
1. **Synchronous conversations** - user messages agent in Slack/Email/GitHub, waits for response
2. **Asynchronous notifications** - agent notifies user in their channel when a background task completes
3. **Seamless escalation** - user can reply to any notification to turn it into a conversation

## Architecture Quick Reference

**Capability-Based Design**: Different channels have different capabilities. Rather than forcing all adapters to implement every feature, we use:

- **Minimal base interface**: All adapters implement `ChannelAdapter` (send, receive, verify)
- **Optional capability interfaces**: Advanced adapters implement `StreamingCapable`, `RichFormattingCapable`, `InteractiveCapable`, `ReactionCapable`
- **Channel-aware execution**: Agent adapts its behavior based on each adapter's declared capabilities

**Channel Comparison:**

| Feature | Slack | Email | GitHub |
|---------|-------|-------|--------|
| Streaming | ✅ | ❌ | ❌ |
| Rich Formatting | ✅ Block Kit | ✅ HTML | ✅ Markdown |
| Interactive Elements | ✅ Buttons/Menus | ❌ | ⚠️ Limited |
| Reactions | ✅ | ❌ | ✅ |
| Preferred Style | Conversational | Comprehensive | Conversational |

---

## Current vs. Proposed Architecture

### Current: Notification-Centric
```
API/Web Interface
    ↓
Agent Execution
    ↓
NotificationService (one-way output only)
    ├→ Email
    ├→ Slack Webhook
    └→ Custom Webhook

Problem: Users must return to the API/Web to continue conversations
```

### Proposed: Channel Adapter-Centric
```
Multiple Conversation Channels
    ├→ Slack App
    ├→ Email (IMAP/SMTP)
    ├→ GitHub App
    ├→ Linear App
    └→ Web API (existing)
         ↓
    ChannelAdapter Layer (bidirectional)
    ├→ receive_message()
    ├→ send_message()
    ├→ link_conversation()
    └→ [channel-specific capabilities]
         ↓
    ConversationManager
    (unified conversation persistence)
         ↓
    Agent Execution (channel-aware)
         ↓
    ChannelAdapter Layer (sends response back to source channel)
```

---

## Use Cases Enabled

### 1. Synchronous Slack Conversation
```
User (in Slack): @AgentBot analyze this dataset
           ↓
SlackChannelAdapter.receive_message()
           ↓
ConversationManager.add_message(conversation_id, USER, "analyze this dataset")
           ↓
AgentExecutor.execute_sync() [streaming, conversational style]
           ↓
SlackChannelAdapter.stream_message_chunk() [real-time updates]
           ↓
User sees agent response in Slack thread
```

### 2. Background Task with Slack Notification
```
API: POST /tasks (delegation task)
           ↓
TaskManager creates task + conversation
           ↓
Task executes in background
           ↓
Agent completes with result
           ↓
SlackChannelAdapter.send_message(conversation_id, "Task completed: ...")
           ↓
User receives Slack message with task result
```

### 3. Seamless Escalation (Notification → Conversation)
```
User receives: "Task completed: Market analysis"
User replies in Slack: "Focus on tech sector trends"
           ↓
SlackChannelAdapter.receive_message() [thread reply]
           ↓
ConversationManager.add_message(conversation_id, USER, "Focus on tech sector trends")
           ↓
Detect continuation pattern → trigger agent
           ↓
AgentExecutor.execute_async() [with full conversation context]
           ↓
SlackChannelAdapter.send_message(conversation_id, "Analyzing tech sector...")
           ↓
Task status updates, Slack notification sent
```

### 4. Email Channel Adapter (Two-Way, Comprehensive Style)
```
User emails agent: "Summarize Q4 revenue report"
           ↓
EmailChannelAdapter.receive_message(email) [via IMAP polling]
           ↓
ConversationManager creates conversation + adds message
           ↓
AgentExecutor.execute_async() [comprehensive message style]
           ↓
EmailChannelAdapter.send_message() [replies with detailed analysis + follow-up questions]
           ↓
User receives comprehensive email reply:
  - Summary
  - Key findings
  - Batched clarifying questions (all at once)
           ↓
User replies to email with all answers
           ↓
Loop continues - full conversation in email threads
```

### 5. GitHub Channel Adapter
```
User comments in issue: "@AgentBot analyze this PR"
           ↓
GitHubChannelAdapter.receive_message(issue_comment)
           ↓
Agent execution with full issue context
           ↓
GitHubChannelAdapter.send_message() [posts reply comment with markdown]
           ↓
User sees agent analysis in issue thread
           ↓
User can continue conversation by replying to agent's comment
```

---

## Channel Adapter Interface

### Design Philosophy: Capability-Based Architecture

Different channels have vastly different capabilities:
- **Slack**: Rich formatting, streaming, interactive buttons, reactions, threading
- **Email**: HTML formatting, attachments, threading via headers, but NO streaming or editing
- **GitHub**: Markdown, code blocks, reactions, but limited interactivity

**Key Insight**: The adapter interface should be **minimal at the base** with **optional capability interfaces** that advanced channels can implement.

### Base Channel Adapter Contract

```python
from abc import ABC, abstractmethod
from typing import Protocol
from enum import Enum
from uuid import UUID

class MessageStyle(Enum):
    """Preferred interaction style for this channel."""
    CONVERSATIONAL = "conversational"  # Quick back-and-forth (Slack)
    COMPREHENSIVE = "comprehensive"    # Detailed, batched messages (Email)

class AdapterCapabilities:
    """Declares what features this channel adapter supports."""
    supports_streaming: bool = False
    supports_threading: bool = True
    supports_rich_formatting: bool = False
    supports_interactive_elements: bool = False
    supports_reactions: bool = False
    supports_message_editing: bool = False
    supports_attachments: bool = False
    preferred_message_style: MessageStyle = MessageStyle.CONVERSATIONAL
    max_message_length: int | None = None

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
        """Verify request authenticity (e.g., Slack signature verification)."""
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

        Returns:
            message_id: ID for message in this channel (for threading)
        """
        pass

    # LINKING
    async def store_conversation_mapping(
        self,
        conversation_id: UUID,
        thread_id: str,
        metadata: dict,
    ) -> None:
        """Store mapping between our conversation ID and channel's thread ID."""
        pass

    async def get_conversation_mapping(self, thread_id: str) -> UUID | None:
        """Look up our conversation ID by channel thread ID."""
        pass
```

### Optional Capability Interfaces

Adapters can implement these Protocol interfaces for advanced features:

```python
class StreamingCapable(Protocol):
    """Adapters that support real-time message updates."""

    async def stream_message_chunk(
        self,
        chunk: str,
        conversation_id: UUID,
        message_id: str
    ) -> None:
        """Stream response chunks. Can update existing message or append."""
        ...

class RichFormattingCapable(Protocol):
    """Adapters that support structured/rich content beyond plain text."""

    async def send_rich_message(
        self,
        content: RichMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with rich formatting (blocks, HTML, etc.)."""
        ...

class InteractiveCapable(Protocol):
    """Adapters that support buttons, forms, menus, etc."""

    async def send_interactive_message(
        self,
        content: InteractiveMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with interactive elements."""
        ...

    async def handle_interaction(
        self,
        interaction_event: dict
    ) -> InteractionResponse:
        """Handle user interaction (button click, menu selection, etc.)."""
        ...

class ReactionCapable(Protocol):
    """Adapters that support reactions/emoji responses."""

    async def add_reaction(
        self,
        message_id: str,
        reaction: str
    ) -> None:
        """Add reaction to a message (for acknowledgment, status, etc.)."""
        ...

    async def remove_reaction(
        self,
        message_id: str,
        reaction: str
    ) -> None:
        """Remove reaction from a message."""
        ...
```

### Slack Channel Adapter Example (Full Featured)

```python
class SlackChannelAdapter(
    ChannelAdapter,
    StreamingCapable,
    RichFormattingCapable,
    InteractiveCapable,
    ReactionCapable
):
    """Full-featured Slack adapter implementing all optional capabilities."""

    def __init__(self, bot_token: str, signing_secret: str):
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.client = AsyncWebClient(token=bot_token)
        self._streaming_messages: dict[str, str] = {}  # Track message_id for updates

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Slack supports nearly everything."""
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
        """Handle Slack event (message, app_mention, etc.)."""
        if event["type"] == "event_callback":
            event_data = event["event"]

            if event_data["type"] == "app_mention":
                return ReceivedMessage(
                    content=event_data["text"].replace("<@BOT_ID>", ""),
                    sender_id=event_data["user"],
                    conversation_id=None,  # New or mapped
                    thread_id=event_data.get("thread_ts", event_data["ts"]),
                    metadata={
                        "channel": event_data["channel"],
                        "ts": event_data["ts"],
                        "thread_ts": event_data.get("thread_ts"),
                    }
                )

    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send plain text message to Slack."""
        response = await self.client.chat_postMessage(
            channel=metadata["channel"],
            text=message,
            thread_ts=metadata.get("thread_ts", metadata.get("ts")),
        )
        return response["ts"]

    # StreamingCapable implementation
    async def stream_message_chunk(
        self,
        chunk: str,
        conversation_id: UUID,
        message_id: str
    ) -> None:
        """Stream chunks by updating existing message."""
        if message_id not in self._streaming_messages:
            self._streaming_messages[message_id] = chunk
        else:
            self._streaming_messages[message_id] += chunk

        await self.client.chat_update(
            channel=...,
            ts=message_id,
            text=self._streaming_messages[message_id],
        )

    # RichFormattingCapable implementation
    async def send_rich_message(
        self,
        content: RichMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with Slack Block Kit formatting."""
        blocks = self._convert_to_blocks(content)
        response = await self.client.chat_postMessage(
            channel=metadata["channel"],
            text=content.fallback_text,
            blocks=blocks,
            thread_ts=metadata.get("thread_ts"),
        )
        return response["ts"]

    # InteractiveCapable implementation
    async def send_interactive_message(
        self,
        content: InteractiveMessage,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send message with buttons/actions."""
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": content.text},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": btn.label},
                        "action_id": btn.action_id,
                        "value": btn.value,
                    }
                    for btn in content.buttons
                ],
            },
        ]
        response = await self.client.chat_postMessage(
            channel=metadata["channel"],
            text=content.text,
            blocks=blocks,
            thread_ts=metadata.get("thread_ts"),
        )
        return response["ts"]

    async def handle_interaction(self, interaction_event: dict) -> InteractionResponse:
        """Handle button clicks, menu selections, etc."""
        action = interaction_event["actions"][0]
        return InteractionResponse(
            conversation_id=...,  # Look up from thread_ts
            action_id=action["action_id"],
            value=action["value"],
            user_id=interaction_event["user"]["id"],
        )

    # ReactionCapable implementation
    async def add_reaction(self, message_id: str, reaction: str) -> None:
        """Add emoji reaction (e.g., 'eyes' for acknowledged, 'white_check_mark' for done)."""
        await self.client.reactions_add(
            channel=self.channel,
            timestamp=message_id,
            name=reaction,
        )

    async def remove_reaction(self, message_id: str, reaction: str) -> None:
        """Remove emoji reaction."""
        await self.client.reactions_remove(
            channel=self.channel,
            timestamp=message_id,
            name=reaction,
        )

    async def verify_request(self, request_data: dict, signature: str, timestamp: str) -> bool:
        """Verify Slack request signature."""
        # Slack signature verification logic
        pass

    def _convert_to_blocks(self, content: RichMessage) -> list[dict]:
        """Convert RichMessage to Slack Block Kit format."""
        # Implementation details...
        pass
```

### Email Channel Adapter Example (Minimal, Comprehensive Style)

```python
class EmailChannelAdapter(ChannelAdapter):
    """Basic email adapter - only implements base interface.

    No streaming, no interactivity, but comprehensive message style.
    """

    def __init__(self, imap_config: dict, smtp_config: dict):
        self.imap_config = imap_config
        self.smtp_config = smtp_config

    @property
    def capabilities(self) -> AdapterCapabilities:
        """Email has limited capabilities compared to Slack."""
        return AdapterCapabilities(
            supports_streaming=False,  # Can't edit sent emails
            supports_threading=True,   # Via In-Reply-To/References headers
            supports_rich_formatting=True,  # HTML emails (could implement RichFormattingCapable)
            supports_interactive_elements=False,
            supports_reactions=False,
            supports_message_editing=False,  # Can't unsend emails
            supports_attachments=True,
            preferred_message_style=MessageStyle.COMPREHENSIVE,  # Detailed messages
            max_message_length=None,  # No hard limit
        )

    async def receive_message(self, email_msg: Message) -> ReceivedMessage:
        """Parse incoming email and extract message."""
        return ReceivedMessage(
            content=email_msg.body,
            sender_id=email_msg.from_addr,
            conversation_id=None,  # Mapped via In-Reply-To header
            thread_id=email_msg.message_id,
            metadata={
                "in_reply_to": email_msg.in_reply_to,
                "subject": email_msg.subject,
                "attachments": email_msg.attachments,
                "from_addr": email_msg.from_addr,
            }
        )

    async def send_message(
        self,
        message: str,
        conversation_id: UUID,
        thread_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Send comprehensive response via SMTP."""
        email = EmailMessage(
            subject=f"Re: {metadata['subject']}",
            body=message,  # Agent will generate comprehensive message
            from_email="agent@platform.com",
            to=[metadata["from_addr"]],
            in_reply_to=thread_id,
        )
        await send_email(email)
        return email.message_id

    async def verify_request(self, request: dict) -> bool:
        """Email doesn't have webhook signatures - validate via IMAP auth."""
        return True  # Already authenticated via IMAP

    # Note: Does NOT implement StreamingCapable, InteractiveCapable, or ReactionCapable
    # Email is intentionally simple - just send/receive
```

---

## Channel-Aware Agent Execution

The agent execution layer adapts its behavior based on channel capabilities. This ensures optimal UX for each platform.

### System Prompt Adaptation

```python
class AgentExecutor:
    """Execute agents with channel-aware behavior."""

    def _build_system_prompt_for_channel(
        self,
        capabilities: AdapterCapabilities
    ) -> str:
        """Adapt system prompt based on channel capabilities."""

        base_prompt = "You are a helpful AI assistant."

        # Adapt for interaction style
        if capabilities.preferred_message_style == MessageStyle.CONVERSATIONAL:
            base_prompt += """

Channel Context: You are communicating via a real-time messaging platform (like Slack).

Guidelines:
- Keep responses concise and conversational
- Ask clarifying questions ONE at a time (user can respond quickly)
- Use short paragraphs and bullet points
- Expect quick back-and-forth dialogue
- Don't overwhelm with too much information at once
"""

        elif capabilities.preferred_message_style == MessageStyle.COMPREHENSIVE:
            base_prompt += """

Channel Context: You are communicating via email or another asynchronous channel.

Guidelines:
- Write comprehensive, detailed responses
- Anticipate follow-up questions and address them proactively
- If you need information, ask ALL clarifying questions in one message
- Structure responses with clear sections and headings
- Include context and explanations - user may not reply immediately
- Be thorough rather than brief
"""

        # Note formatting capabilities
        if capabilities.supports_rich_formatting:
            base_prompt += "\n- You can use rich formatting (markdown, HTML, etc.)"

        return base_prompt

    async def execute_with_channel_context(
        self,
        conversation_id: UUID,
        user_message: str,
        adapter: ChannelAdapter,
    ):
        """Execute agent with channel-specific adaptations."""

        caps = adapter.capabilities

        # Build channel-aware system prompt
        system_prompt = self._build_system_prompt_for_channel(caps)

        # Get conversation history
        messages = await self.conversation_manager.get_messages(conversation_id)

        # Execute agent
        result = await self.agent.run(
            user_message,
            message_history=messages,
            system_prompt=system_prompt,
        )

        # Route response based on capabilities
        if caps.supports_streaming and isinstance(adapter, StreamingCapable):
            # Acknowledge receipt with reaction if possible
            if isinstance(adapter, ReactionCapable):
                await adapter.add_reaction(message_id, "eyes")

            # Stream response
            message_id = None
            async for chunk in result.stream():
                if message_id is None:
                    # Start new message
                    message_id = await adapter.send_message("", conversation_id, ...)

                await adapter.stream_message_chunk(chunk, conversation_id, message_id)

            # Mark complete
            if isinstance(adapter, ReactionCapable):
                await adapter.add_reaction(message_id, "white_check_mark")
        else:
            # Send complete message
            full_response = result.text
            await adapter.send_message(full_response, conversation_id, ...)

        return result
```

### Interaction Style Examples

#### Slack (Conversational)
```
User: Help me analyze this dataset
Agent: I'd be happy to help! What format is the data in?

User: CSV file
Agent: Great! Could you share the file or a link to it?

User: [uploads file]
Agent: 👀 [reaction added - acknowledged]
Agent: [streaming] Analyzing the CSV... I can see it has 5 columns and 1,200 rows.
      What specific insights are you looking for?

User: Revenue trends over time
Agent: [streaming] I'll create a time series analysis of your revenue data...
      [chart appears]
      📊 Key findings:
      • 15% growth in Q4
      • Seasonal peaks in March and November
      • One anomaly in August (worth investigating)
Agent: ✅ [reaction added - complete]
```

#### Email (Comprehensive)
```
User: Help me analyze this dataset

Agent: Subject: Re: Dataset Analysis Request

Hello,

I'd be happy to help analyze your dataset. To provide the most valuable
analysis, I need some additional information:

1. **Data Format & Access**
   - What format is the data in? (CSV, Excel, JSON, database, etc.)
   - How can I access it? (attachment, link, API, etc.)
   - Approximate size of the dataset?

2. **Analysis Objectives**
   What are you hoping to learn? For example:
   - Revenue/sales trends over time
   - Customer segmentation patterns
   - Forecasting future values
   - Anomaly detection
   - Correlation between variables
   - Other (please specify)

3. **Context**
   - What time period does the data cover?
   - Are there specific metrics or KPIs you track?
   - Any known data quality issues I should be aware of?
   - What will you use this analysis for? (helps me focus on relevant insights)

4. **Output Preferences**
   - Do you prefer visualizations, statistical summaries, or both?
   - Any specific format for deliverables?

Please provide as much detail as possible in your reply, and I'll prepare
a comprehensive analysis for you.

Best regards,
AI Agent
```

Notice how the same user request gets completely different response styles based on the channel's `preferred_message_style` capability.

---

## Database Schema Changes

### New Table: `conversation_channel_adapters`
Tracks which channel adapters a conversation is active in.

```python
class ConversationChannelAdapterDB(Base):
    __tablename__ = "conversation_channel_adapters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("conversations.id"))
    adapter_name: Mapped[str] = mapped_column(String(50))  # "slack", "email", "github"
    thread_id: Mapped[str] = mapped_column(String(500))    # Adapter's thread/conversation ID
    metadata: Mapped[dict] = mapped_column(JSON)           # Channel-specific data
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Indexes for efficient lookups
    __table_args__ = (
        Index('ix_adapter_thread', 'adapter_name', 'thread_id'),
        UniqueConstraint('adapter_name', 'thread_id', name='uq_adapter_thread'),
    )
```

### Updated: `messages` table
Add adapter tracking to messages:

```python
class MessageDB(Base):
    # ... existing fields ...

    # Which adapter this message came from
    adapter_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    adapter_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

---

## API/Integration Points

### 1. Slack Event Webhook
```
POST /channel-adapters/slack/events
Headers: X-Slack-Request-Timestamp, X-Slack-Signature
Body: Slack event payload

Handles:
- app_mention
- message_threads
- message_edits
- reactions (for interactive feedback)
```

### 2. Email Receiver (Polling)
```
Background job that periodically:
- Connects via IMAP
- Checks for new emails to agent mailbox
- Calls EmailChannelAdapter.receive_message()
- Adds to conversation
- Triggers agent execution with COMPREHENSIVE message style
```

### 3. GitHub Webhook
```
POST /channel-adapters/github/webhooks
Body: GitHub event (issue_comment, pull_request_review_comment)

Handles:
- New mentions in issues/PRs
- Replies to agent's comments
```

### 4. Slack Interactivity Endpoint
```
POST /channel-adapters/slack/interactions
Headers: X-Slack-Request-Timestamp, X-Slack-Signature
Body: Interaction payload (button clicks, menu selections)

Handles:
- Button clicks from interactive messages
- Menu selections
- Routes to SlackChannelAdapter.handle_interaction()
```

---

## Service Layer Changes

### New: `ChannelAdapterManager`
Routes messages between channel adapters and conversations.

```python
class ChannelAdapterManager:
    """Manages channel adapter registration and message routing."""

    def __init__(self):
        self._adapters: dict[str, ChannelAdapter] = {}

    async def register_adapter(self, name: str, adapter: ChannelAdapter) -> None:
        """Register a new channel adapter."""
        self._adapters[name] = adapter

    def get_adapter(self, name: str) -> ChannelAdapter:
        """Get a registered adapter by name."""
        return self._adapters[name]

    async def handle_incoming_event(
        self,
        adapter_name: str,
        event_data: dict,
    ) -> None:
        """Route incoming message from adapter to conversation."""
        adapter = self.get_adapter(adapter_name)

        # 1. Verify request authenticity
        if not await adapter.verify_request(event_data):
            raise SecurityError("Invalid request signature")

        # 2. Parse message via adapter
        message = await adapter.receive_message(event_data)

        # 3. Look up or create conversation
        conversation_id = await adapter.get_conversation_mapping(message.thread_id)
        if conversation_id is None:
            conversation_id = await self._create_conversation(adapter_name, message)

        # 4. Add message to conversation
        await self.conversation_manager.add_message_from_adapter(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=message.content,
            adapter_name=adapter_name,
            adapter_message_id=message.thread_id,
        )

        # 5. Determine if response needed (sync vs. async)
        # 6. Execute agent with channel context
        await self.agent_executor.execute_with_channel_context(
            conversation_id=conversation_id,
            user_message=message.content,
            adapter=adapter,
        )

    async def send_to_adapter(
        self,
        conversation_id: UUID,
        message: str,
        adapter_name: str,
    ) -> None:
        """Send message to conversation's channel adapter."""
        adapter = self.get_adapter(adapter_name)

        # Get adapter mapping for this conversation
        mapping = await self._get_adapter_mapping(conversation_id, adapter_name)

        # Send via adapter
        await adapter.send_message(
            message=message,
            conversation_id=conversation_id,
            thread_id=mapping.thread_id,
            metadata=mapping.metadata,
        )
```

### Updated: `ConversationManager`
Add channel adapter-aware methods.

```python
class ConversationManager:
    async def add_message_from_adapter(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        adapter_name: str,
        adapter_message_id: str,
    ) -> Message:
        """Add message and track which channel adapter it came from."""
        pass

    async def get_conversation_channel_adapters(
        self, conversation_id: UUID
    ) -> list[ConversationChannelAdapter]:
        """Get all active channel adapters for a conversation."""
        pass
```

---

## Flow: Receiving a Message

```
Slack user mentions agent
        ↓
POST /channel-adapters/slack/events
        ↓
SlackChannelAdapter.verify_request()
        ↓
SlackChannelAdapter.receive_message() → ReceivedMessage
        ↓
ChannelAdapterManager.handle_incoming_event()
        ↓
Is this a continuation of existing conversation?
├─ YES: Lookup conversation_id via thread_id
└─ NO: Create new conversation
        ↓
ConversationManager.add_message_from_adapter()
        ↓
AgentExecutor.execute_with_channel_context()
├─ Build channel-aware system prompt
├─ Check adapter capabilities
└─ Route response appropriately
        ↓
If supports_streaming:
├─ SlackChannelAdapter.add_reaction("eyes")
├─ Stream chunks → SlackChannelAdapter.stream_message_chunk()
└─ SlackChannelAdapter.add_reaction("white_check_mark")

If not supports_streaming:
└─ Send complete message → EmailChannelAdapter.send_message()
```

---

## Configuration

### New: Adapter Configuration
```env
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_ENABLED=true

# Email
EMAIL_ADAPTER_ENABLED=true
EMAIL_IMAP_HOST=imap.gmail.com
EMAIL_IMAP_USERNAME=agent@gmail.com
EMAIL_IMAP_PASSWORD=...
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_USERNAME=agent@gmail.com
EMAIL_SMTP_PASSWORD=...

# GitHub
GITHUB_APP_ID=...
GITHUB_PRIVATE_KEY=...
GITHUB_ENABLED=true

# Linear (example future adapter)
LINEAR_API_KEY=...
LINEAR_ENABLED=false
```

---

## Design Benefits

| Aspect | Benefit |
|--------|---------|
| **User Experience** | Users stay in their preferred channels (Slack, Email, GitHub) |
| **Channel-Optimized** | Agent adapts interaction style to each channel's strengths |
| **Scalability** | Easy to add new channel adapters without changing core logic |
| **Flexibility** | Same agent execution engine supports all channels |
| **No Artificial Limits** | Advanced channels (Slack) can use full platform capabilities |
| **Simple When Needed** | Basic channels (Email) don't need unused complex features |
| **Continuity** | Seamless escalation from notification → conversation |
| **Auditability** | Track which channel messages come from |
| **Type Safety** | Protocol-based capabilities enable compile-time checking |
| **Extensibility** | New capabilities = new Protocol interface (doesn't break existing adapters) |

---

## Implementation Phases

### Phase 0: Core Infrastructure
- [ ] Define `ChannelAdapter` base class (minimal interface)
- [ ] Define capability Protocol interfaces (`StreamingCapable`, `RichFormattingCapable`, etc.)
- [ ] Create `AdapterCapabilities` dataclass
- [ ] Define `MessageStyle` enum
- [ ] Add `conversation_channel_adapters` table
- [ ] Implement `ChannelAdapterManager`

### Phase 1: Channel-Aware Agent Execution
- [ ] Update `AgentExecutor.execute_with_channel_context()`
- [ ] Implement `_build_system_prompt_for_channel()`
- [ ] Add capability detection logic (isinstance checks)
- [ ] Route responses based on capabilities (streaming vs. complete)
- [ ] Update `ConversationManager` for channel adapter awareness

### Phase 2: Slack Channel Adapter (Full Featured)
- [ ] Implement `SlackChannelAdapter` base interface
- [ ] Implement `StreamingCapable` (message updates)
- [ ] Implement `RichFormattingCapable` (Block Kit)
- [ ] Implement `InteractiveCapable` (buttons, menus)
- [ ] Implement `ReactionCapable` (emoji reactions)
- [ ] Set up Slack app OAuth/credentials
- [ ] Create `/channel-adapters/slack/events` endpoint
- [ ] Create `/channel-adapters/slack/interactions` endpoint
- [ ] Test conversational interaction style

### Phase 3: Email Channel Adapter (Minimal)
- [ ] Implement `EmailChannelAdapter` (base interface only)
- [ ] Set up IMAP polling background job
- [ ] Set up SMTP sending
- [ ] Test comprehensive message style
- [ ] Verify thread continuity via In-Reply-To headers
- [ ] Optional: Implement `RichFormattingCapable` for HTML emails

### Phase 4: Additional Adapters
- [ ] GitHub channel adapter (webhooks + markdown)
- [ ] Linear channel adapter (API)
- [ ] Document how to create custom channel adapters
- [ ] Create adapter capability matrix documentation

### Phase 5: Advanced Features
- [ ] Multi-adapter conversations (single conversation across multiple channels)
- [ ] User identity mapping across channels
- [ ] Adapter health monitoring and failover
- [ ] Rate limiting per channel adapter
- [ ] Adapter-specific error handling and retry logic

---

## Questions for Design Exploration

### Resolved by Capability-Based Design

1. ~~**Message Formatting**~~: ✅ Solved via capability Protocols - each adapter implements only what it supports

2. ~~**Interaction Style Differences**~~: ✅ Solved via `preferred_message_style` - agent adapts behavior per channel

### Still Open

3. **Synchronous vs. Asynchronous**: Should Slack messages auto-trigger agent execution (sync), or only when explicitly prompted?
   - **Proposal**: Use pattern detection - direct mentions = sync, background tasks = async

4. **Rate Limiting**: How do we prevent channel adapter abuse?
   - **Proposal**: Per-user-per-adapter quotas stored in Redis with exponential backoff

5. **State Management**: For adapters that support threading (Slack, email), how do we handle out-of-order messages?
   - **Proposal**: Use message timestamps + deduplication windows, store `adapter_message_id` for idempotency

6. **Context Window**: How do we handle conversation history when channels have different limits?
   - **Proposal**: Truncate or summarize older messages based on `max_message_length` capability

7. **Multi-Adapter Continuity**: If a conversation spans multiple adapters (starts in Slack, continues in email), how do we maintain context?
   - **Major Open Question**: Requires cross-adapter identity linking
   - **Proposal**: Start with single-adapter-per-conversation constraint, add multi-adapter later if needed

8. **Adapter Lifecycle**: How do we handle adapter failures, disconnections, or credential expiry?
   - **Proposal**: Add `adapter_status` field, health checks, and retry/fallback policies

9. **Identity Mapping**: How do we link external identities (Slack user ID, email address) to platform user accounts?
   - **Missing Component**: Need `UserIdentityMapper` service

---

## Conclusion

This channel adapter pattern fundamentally shifts the architecture from "notifications sent to users" to "conversations happening in user channels." It enables the three interaction patterns (synchronous, asynchronous, seamless escalation) and creates a scalable, extensible system for multi-channel agent interaction.

### Key Insights

1. **Channel adapters aren't notification channels—they're conversation channels**. The agent doesn't just notify users; it participates in conversations wherever users already work.

2. **Channels have vastly different capabilities**. A capability-based design with optional Protocol interfaces allows:
   - Advanced channels (Slack) to use full platform capabilities
   - Basic channels (Email) to stay simple without unused complexity
   - New capabilities to be added without breaking existing adapters

3. **Interaction style should match the channel**. The same agent request gets different responses:
   - Slack: Conversational, iterative, quick back-and-forth
   - Email: Comprehensive, batched questions, anticipate follow-ups

4. **Type safety matters**. Using Protocols for capability detection (`isinstance(adapter, StreamingCapable)`) provides compile-time checking and clear contracts.

### Architecture Summary

```
User Message (any channel)
    ↓
ChannelAdapter receives + verifies
    ↓
ChannelAdapterManager routes to conversation
    ↓
AgentExecutor adapts behavior based on capabilities
    ↓
ChannelAdapter sends response (with channel-specific features)
```

This design creates a foundation for agents that feel native to each platform, rather than forcing users into a one-size-fits-all interaction model.
