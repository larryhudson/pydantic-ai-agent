"""API endpoints for task management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.domain import (
    CreateTaskRequest,
    Task,
    TaskType,
    UpdateTaskRequest,
)
from app.services.task_manager import TaskManager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=Task)
async def create_task(
    request: CreateTaskRequest,
    user_id: str = "default_user",  # In production, get from auth
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Create a new task.

    Args:
        request: Task creation request
        user_id: User identifier (from authentication)
        db: Database session

    Returns:
        Created task
    """
    manager = TaskManager(db)
    task = await manager.create_task(
        user_id=user_id,
        task_type=request.task_type,
        prompt=request.prompt,
        schedule_expression=request.schedule_expression,
        trigger_config=request.trigger_config,
        notification_config=request.notification_config,
    )
    return task


@router.get("", response_model=list[Task])
async def list_tasks(
    task_type: TaskType | None = None,
    is_active: bool | None = None,
    user_id: str = "default_user",  # In production, get from auth
    db: AsyncSession = Depends(get_db),
) -> list[Task]:
    """List all tasks for the current user.

    Args:
        task_type: Optional filter by task type
        is_active: Optional filter by active status
        user_id: User identifier (from authentication)
        db: Database session

    Returns:
        List of tasks
    """
    manager = TaskManager(db)
    tasks = await manager.list_user_tasks(user_id, task_type=task_type, is_active=is_active)
    return tasks


@router.get("/{task_id}", response_model=Task)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Get task details by ID.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Task details

    Raises:
        HTTPException: If task not found
    """
    manager = TaskManager(db)
    task = await manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.patch("/{task_id}", response_model=Task)
async def update_task(
    task_id: UUID,
    request: UpdateTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> Task:
    """Update task configuration.

    Args:
        task_id: Task identifier
        request: Update request
        db: Database session

    Returns:
        Updated task

    Raises:
        HTTPException: If task not found
    """
    manager = TaskManager(db)

    try:
        task = await manager.update_task(
            task_id=task_id,
            prompt=request.prompt,
            schedule_expression=request.schedule_expression,
            is_active=request.is_active,
            notification_config=request.notification_config,
        )
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{task_id}")
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a task.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If task not found
    """
    manager = TaskManager(db)

    try:
        await manager.delete_task(task_id)
        return {"message": "Task deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{task_id}/execute")
async def execute_task_now(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger task execution (for testing).

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Success message
    """
    manager = TaskManager(db)

    # Execute task in background (in production, this would queue the task)
    await manager.execute_task(task_id)

    return {"message": "Task execution started"}


@router.post("/{task_id}/disable")
async def disable_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Disable a scheduled or triggered task.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If task not found
    """
    manager = TaskManager(db)

    try:
        await manager.disable_task(task_id)
        return {"message": "Task disabled successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# Webhook endpoint for event-triggered tasks
@router.post("/webhooks/{task_id}")
async def webhook_trigger(
    task_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Receive webhook to trigger event-driven task.

    Args:
        task_id: Task identifier
        payload: Webhook payload
        db: Database session

    Returns:
        Success message
    """
    manager = TaskManager(db)

    # Execute task with webhook payload as context
    # In production, this would queue the task
    await manager.execute_task(task_id)

    return {"message": "Webhook received and task queued"}
