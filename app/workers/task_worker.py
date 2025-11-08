"""ARQ background worker for executing tasks."""

import logging
from typing import ClassVar
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)
settings = get_settings()


async def execute_task_job(ctx: dict, task_id: str) -> None:
    """Background job to execute a task.

    This function is called by the ARQ worker to process tasks asynchronously.

    Args:
        ctx: ARQ context
        task_id: Task identifier (as string)
    """
    task_uuid = UUID(task_id)
    logger.info(f"Executing task {task_uuid}")

    async with AsyncSessionLocal() as db:
        manager = TaskManager(db)
        await manager.execute_task(task_uuid)

    logger.info(f"Task {task_uuid} execution completed")


async def enqueue_task(task_id: UUID) -> None:
    """Enqueue a task for background execution.

    Args:
        task_id: Task identifier
    """
    redis = await create_pool(
        RedisSettings.from_dsn(settings.arq_redis_url),
    )

    job = await redis.enqueue_job("execute_task_job", str(task_id))
    if job:
        logger.info(f"Task {task_id} enqueued as job {job.job_id}")
    else:
        logger.warning(f"Failed to enqueue task {task_id}")


# ARQ Worker Configuration
class WorkerSettings:
    """Configuration for ARQ worker."""

    functions: ClassVar = [execute_task_job]
    redis_settings: ClassVar = RedisSettings.from_dsn(settings.arq_redis_url)
    max_jobs: ClassVar = settings.max_worker_jobs
    job_timeout: ClassVar = 600  # 10 minutes
    keep_result: ClassVar = 3600  # Keep results for 1 hour
