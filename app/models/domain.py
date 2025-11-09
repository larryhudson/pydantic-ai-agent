"""Core domain models using Pydantic."""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Get current UTC time with timezone awareness."""
    return datetime.now(UTC)


# Enums
class ConversationStatus(str, Enum):
    """Status of a conversation thread."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class MessageRole(str, Enum):
    """Role of a message in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TaskType(str, Enum):
    """Type of background task."""

    DELEGATION = "delegation"  # One-time background task
    SCHEDULED = "scheduled"  # Recurring on schedule
    TRIGGERED = "triggered"  # Event-driven


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Waiting for user input


class NotificationChannel(str, Enum):
    """Notification delivery channel."""

    EMAIL = "email"
    SLACK = "slack"
    PUSH = "push"
    WEBHOOK = "webhook"


# Domain Models
class NotificationConfig(BaseModel):
    """Configuration for task notifications."""

    channels: list[NotificationChannel] = Field(default_factory=list)
    email_address: str | None = None
    slack_webhook_url: str | None = None
    webhook_url: str | None = None


class Message(BaseModel):
    """Individual message within a conversation."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=utc_now)

    # Tool usage tracking
    tool_calls: list[dict] | None = None
    tool_results: list[dict] | None = None


class ConversationThread(BaseModel):
    """Conversation thread representing any agent interaction."""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: ConversationStatus = ConversationStatus.ACTIVE

    # Pattern identification
    pattern_type: str  # "chatbot", "delegation", "scheduled", "triggered", "research"

    # Context and state
    context_data: dict = Field(default_factory=dict)

    # Message history (loaded separately on demand)
    messages: list[Message] = Field(default_factory=list)

    # Task-specific metadata
    task_id: UUID | None = None


class Task(BaseModel):
    """Represents delegated, scheduled, or triggered work."""

    id: UUID = Field(default_factory=uuid4)
    user_id: str
    conversation_id: UUID

    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING

    # Task definition
    prompt: str
    agent_config: dict = Field(default_factory=dict)

    # Scheduling (for scheduled tasks)
    schedule_expression: str | None = None

    # Event triggers (for triggered tasks)
    trigger_config: dict | None = None

    # Execution tracking
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    # Notifications
    notification_config: NotificationConfig = Field(default_factory=NotificationConfig)

    # State
    is_active: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# Request/Response Models for API
class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    pattern_type: str
    context_data: dict = Field(default_factory=dict)


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""

    message: str
    stream: bool = False


class CreateTaskRequest(BaseModel):
    """Request to create a new task."""

    task_type: TaskType
    prompt: str
    schedule_expression: str | None = None
    trigger_config: dict | None = None
    notification_config: NotificationConfig | None = None


class UpdateTaskRequest(BaseModel):
    """Request to update a task."""

    prompt: str | None = None
    schedule_expression: str | None = None
    is_active: bool | None = None
    notification_config: NotificationConfig | None = None


# Channel Adapter Models
class ConversationChannelAdapter(BaseModel):
    """Tracks which channel adapters a conversation is active in."""

    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    adapter_name: str  # "slack", "email", "github"
    thread_id: str  # Adapter's thread/conversation ID
    metadata: dict = Field(default_factory=dict, description="Channel-specific data")
    created_at: datetime = Field(default_factory=utc_now)
