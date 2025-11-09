"""Service for managing tasks (delegated, scheduled, or triggered)."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from pydantic_ai import Agent
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationDB, TaskDB
from app.models.domain import (
    NotificationConfig,
    Task,
    TaskStatus,
    TaskType,
)
from app.services.agent_executor import AgentExecutor
from app.services.conversation_manager import ConversationManager
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task lifecycle: creation, execution, status tracking."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self.conversation_manager = ConversationManager(db)
        self.notification_service = NotificationService()

    async def create_task(
        self,
        user_id: str,
        task_type: TaskType,
        prompt: str,
        schedule_expression: str | None = None,
        trigger_config: dict | None = None,
        notification_config: NotificationConfig | None = None,
        agent_config: dict | None = None,
    ) -> Task:
        """Create a new task with associated conversation thread.

        Args:
            user_id: User identifier
            task_type: Type of task (delegation, scheduled, triggered)
            prompt: Task prompt/instruction
            schedule_expression: Cron expression for scheduled tasks
            trigger_config: Configuration for triggered tasks
            notification_config: Notification settings
            agent_config: Agent configuration

        Returns:
            Created task
        """
        # Create conversation thread for this task
        pattern_type = self._get_pattern_type(task_type)
        conversation = await self.conversation_manager.create_conversation(
            user_id=user_id, pattern_type=pattern_type
        )

        # Create task
        task_db = TaskDB(
            user_id=user_id,
            conversation_id=conversation.id,
            task_type=task_type,
            prompt=prompt,
            schedule_expression=schedule_expression,
            trigger_config=trigger_config or {},
            agent_config=agent_config or {},
            notification_channels=(
                [str(c.value) for c in notification_config.channels] if notification_config else []
            ),
            notification_email=notification_config.email_address if notification_config else None,
            notification_slack_webhook=(
                notification_config.slack_webhook_url if notification_config else None
            ),
            notification_webhook_url=(
                notification_config.webhook_url if notification_config else None
            ),
        )

        self.db.add(task_db)
        await self.db.commit()
        await self.db.refresh(task_db)

        # Update conversation with task_id
        await self.db.execute(
            update(ConversationDB)
            .where(ConversationDB.id == conversation.id)
            .values(task_id=task_db.id)
        )
        await self.db.commit()

        return self._to_domain(task_db)

    async def execute_task(self, task_id: UUID, agent: Agent | None = None) -> None:
        """Execute a task (called by scheduler or webhook).

        Args:
            task_id: Task identifier
            agent: Optional agent instance (if None, creates default)
        """
        # Get task
        task_db = await self.db.get(TaskDB, task_id)
        if not task_db:
            logger.error(f"Task {task_id} not found")
            return

        if not task_db.is_active:
            logger.info(f"Task {task_id} is disabled, skipping execution")
            return

        # Update status to running
        task_db.status = TaskStatus.RUNNING
        task_db.started_at = datetime.now(UTC)
        await self.db.commit()

        try:
            # Create or use provided agent
            if agent is None:
                from app.services.agent_executor import create_default_agent

                agent = create_default_agent()

            # Execute agent
            agent_executor = AgentExecutor(agent, self.db)
            result = await agent_executor.execute_async(
                conversation_id=task_db.conversation_id, prompt=task_db.prompt
            )

            # Update status to completed
            task_db.status = TaskStatus.COMPLETED
            task_db.completed_at = datetime.now(UTC)
            task_db.last_run_at = datetime.now(UTC)
            task_db.error_message = None
            await self.db.commit()

            # Send success notification
            task = self._to_domain(task_db)
            await self.notification_service.notify_task_complete(task, result)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)

            # Update status to failed
            task_db.status = TaskStatus.FAILED
            task_db.completed_at = datetime.now(UTC)
            task_db.error_message = str(e)
            await self.db.commit()

            # Send failure notification
            task = self._to_domain(task_db)
            await self.notification_service.notify_task_failed(task, str(e))

    async def get_task(self, task_id: UUID) -> Task | None:
        """Get task by ID.

        Args:
            task_id: Task identifier

        Returns:
            Task or None if not found
        """
        task_db = await self.db.get(TaskDB, task_id)
        if not task_db:
            return None
        return self._to_domain(task_db)

    async def list_user_tasks(
        self, user_id: str, task_type: TaskType | None = None, is_active: bool | None = None
    ) -> list[Task]:
        """List all tasks for a user.

        Args:
            user_id: User identifier
            task_type: Optional filter by task type
            is_active: Optional filter by active status

        Returns:
            List of tasks
        """
        query = select(TaskDB).where(TaskDB.user_id == user_id)

        if task_type:
            query = query.where(TaskDB.task_type == task_type)

        if is_active is not None:
            query = query.where(TaskDB.is_active == is_active)

        query = query.order_by(TaskDB.created_at.desc())

        result = await self.db.execute(query)
        tasks_db = result.scalars().all()

        return [self._to_domain(task) for task in tasks_db]

    async def update_task(
        self,
        task_id: UUID,
        prompt: str | None = None,
        schedule_expression: str | None = None,
        is_active: bool | None = None,
        notification_config: NotificationConfig | None = None,
    ) -> Task:
        """Update task configuration.

        Args:
            task_id: Task identifier
            prompt: New prompt
            schedule_expression: New schedule expression
            is_active: New active status
            notification_config: New notification configuration

        Returns:
            Updated task

        Raises:
            ValueError: If task not found
        """
        task_db = await self.db.get(TaskDB, task_id)
        if not task_db:
            raise ValueError(f"Task {task_id} not found")

        if prompt is not None:
            task_db.prompt = prompt

        if schedule_expression is not None:
            task_db.schedule_expression = schedule_expression

        if is_active is not None:
            task_db.is_active = is_active

        if notification_config is not None:
            task_db.notification_channels = [str(c.value) for c in notification_config.channels]
            task_db.notification_email = notification_config.email_address
            task_db.notification_slack_webhook = notification_config.slack_webhook_url
            task_db.notification_webhook_url = notification_config.webhook_url

        task_db.updated_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(task_db)

        return self._to_domain(task_db)

    async def disable_task(self, task_id: UUID) -> None:
        """Disable a scheduled or triggered task.

        Args:
            task_id: Task identifier
        """
        task_db = await self.db.get(TaskDB, task_id)
        if not task_db:
            raise ValueError(f"Task {task_id} not found")

        task_db.is_active = False
        task_db.updated_at = datetime.now(UTC)
        await self.db.commit()

    async def delete_task(self, task_id: UUID) -> None:
        """Delete a task.

        Args:
            task_id: Task identifier
        """
        task_db = await self.db.get(TaskDB, task_id)
        if not task_db:
            raise ValueError(f"Task {task_id} not found")

        await self.db.delete(task_db)
        await self.db.commit()

    @staticmethod
    def _get_pattern_type(task_type: TaskType) -> str:
        """Get conversation pattern type from task type."""
        mapping = {
            TaskType.DELEGATION: "delegation",
            TaskType.SCHEDULED: "scheduled",
            TaskType.TRIGGERED: "triggered",
        }
        return mapping.get(task_type, "delegation")

    @staticmethod
    def _to_domain(task_db: TaskDB) -> Task:
        """Convert database model to domain model."""
        from app.models.domain import NotificationChannel

        # Reconstruct notification config
        notification_config = NotificationConfig(
            channels=[NotificationChannel(ch) for ch in task_db.notification_channels],
            email_address=task_db.notification_email,
            slack_webhook_url=task_db.notification_slack_webhook,
            webhook_url=task_db.notification_webhook_url,
        )

        return Task(
            id=task_db.id,
            user_id=task_db.user_id,
            conversation_id=task_db.conversation_id,
            task_type=task_db.task_type,
            status=task_db.status,
            prompt=task_db.prompt,
            agent_config=task_db.agent_config,
            schedule_expression=task_db.schedule_expression,
            trigger_config=task_db.trigger_config,
            started_at=task_db.started_at,
            completed_at=task_db.completed_at,
            error_message=task_db.error_message,
            notification_config=notification_config,
            is_active=task_db.is_active,
            last_run_at=task_db.last_run_at,
            next_run_at=task_db.next_run_at,
            created_at=task_db.created_at,
            updated_at=task_db.updated_at,
        )
