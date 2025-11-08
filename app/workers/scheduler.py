"""Task scheduler using APScheduler for scheduled tasks."""

import logging
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)
settings = get_settings()

# Global scheduler instance
scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)


async def execute_scheduled_task(task_id: str) -> None:
    """Execute a scheduled task.

    This function is called by APScheduler at the scheduled time.

    Args:
        task_id: Task identifier (as string)
    """
    task_uuid = UUID(task_id)
    logger.info(f"Executing scheduled task {task_uuid}")

    async with AsyncSessionLocal() as db:
        manager = TaskManager(db)
        await manager.execute_task(task_uuid)

    logger.info(f"Scheduled task {task_uuid} execution completed")


def schedule_task(task_id: UUID, cron_expression: str) -> None:
    """Add a scheduled task to the scheduler.

    Args:
        task_id: Task identifier
        cron_expression: Cron expression (e.g., "0 9 * * *" for daily at 9 AM)
    """
    job_id = f"task_{task_id}"

    # Remove existing job if it exists
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Add new job
    scheduler.add_job(
        func=execute_scheduled_task,
        trigger=CronTrigger.from_crontab(cron_expression),
        args=[str(task_id)],
        id=job_id,
        replace_existing=True,
    )

    logger.info(f"Scheduled task {task_id} with cron expression: {cron_expression}")


def unschedule_task(task_id: UUID) -> None:
    """Remove a task from the scheduler.

    Args:
        task_id: Task identifier
    """
    job_id = f"task_{task_id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Unscheduled task {task_id}")


def start_scheduler() -> None:
    """Start the scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def load_scheduled_tasks() -> None:
    """Load all active scheduled tasks from database and add them to scheduler.

    This should be called on application startup.
    """
    from app.models.domain import TaskType

    async with AsyncSessionLocal() as db:
        manager = TaskManager(db)

        # Get all active scheduled tasks for all users
        # Note: In production, you might want to paginate or limit this
        tasks = await manager.list_user_tasks(
            user_id="",  # Empty to get all users' tasks
            task_type=TaskType.SCHEDULED,
            is_active=True,
        )

        for task in tasks:
            if task.schedule_expression:
                schedule_task(task.id, task.schedule_expression)

        logger.info(f"Loaded {len(tasks)} scheduled tasks")
