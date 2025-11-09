"""SQLAlchemy ORM models for database persistence."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.domain import (
    ConversationStatus,
    MessageRole,
    TaskStatus,
    TaskType,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class ConversationDB(Base):
    """Database model for conversation threads."""

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), nullable=False, default=ConversationStatus.ACTIVE
    )

    # Pattern identification
    # TODO: Split pattern_type into three orthogonal fields:
    #   - execution_pattern: "sync", "delegation", "scheduled", "triggered"
    #   - origin: "api", "channel", "cli"
    #   - channel_type: "slack", "email", "github" (if origin=="channel")
    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Context and state
    context_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Task-specific metadata
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)

    # Relationships
    messages: Mapped[list["MessageDB"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )
    task: Mapped["TaskDB | None"] = relationship(back_populates="conversation")


class MessageDB(Base):
    """Database model for messages within conversations."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Tool usage tracking
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    tool_results: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    # Channel adapter tracking
    adapter_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    adapter_message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    conversation: Mapped[ConversationDB] = relationship(back_populates="messages")


class TaskDB(Base):
    """Database model for tasks (delegated, scheduled, or triggered)."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, unique=True
    )

    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True
    )

    # Task definition
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    agent_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Scheduling (for scheduled tasks)
    schedule_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Event triggers (for triggered tasks)
    trigger_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Execution tracking
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Notifications
    notification_channels: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )  # List of NotificationChannel values
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notification_slack_webhook: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notification_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    conversation: Mapped[ConversationDB] = relationship(back_populates="task")


class ConversationChannelAdapterDB(Base):
    """Database model tracking which channel adapters a conversation is active in."""

    __tablename__ = "conversation_channel_adapters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    adapter_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "slack", "email", "github"
    thread_id: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # Adapter's thread/conversation ID
    adapter_metadata: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )  # Channel-specific data
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Indexes for efficient lookups
    __table_args__ = (
        Index("ix_adapter_thread", "adapter_name", "thread_id"),
        UniqueConstraint("adapter_name", "thread_id", name="uq_adapter_thread"),
    )
