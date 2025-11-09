"""ARQ background worker for executing tasks."""

import logging
from typing import ClassVar
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings, create_agent_runner
from app.database import AsyncSessionLocal
from app.services.channel_adapter_manager import ChannelAdapterManager, initialize_adapters
from app.services.agent_executor import AgentExecutor
from app.services.conversation_manager import ConversationManager
from app.services.task_manager import TaskManager

# Configure logging (worker process doesn't inherit from main.py)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

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


async def process_conversation_job(ctx: dict, conversation_id: str) -> None:
    """Background job to process a conversation with agent execution.

    Executes the agent on the latest message and sends the response
    back through the appropriate adapter.

    Args:
        ctx: ARQ context
        conversation_id: Conversation identifier
    """
    conversation_uuid = UUID(conversation_id)
    logger.info(f"Processing conversation {conversation_uuid}")

    try:
        # Initialize adapters (in case this is the first time the worker is running)
        await initialize_adapters()

        async with AsyncSessionLocal() as db:
            conversation_manager = ConversationManager(db)
            adapter_manager = ChannelAdapterManager(db)

            # Get conversation
            conversation = await conversation_manager.get_conversation(conversation_uuid)
            if not conversation:
                logger.error(f"Conversation {conversation_uuid} not found")
                return

            # Execute agent on the existing conversation
            runner = create_agent_runner()
            executor = AgentExecutor(runner, conversation_manager)
            response = await executor.execute_on_existing_conversation(conversation_uuid)

            # Get adapter info from conversation context
            context_data = conversation.context_data or {}
            adapter_name = context_data.get("adapter_name")

            if adapter_name:
                try:
                    # Get adapter and mapping
                    adapter = adapter_manager.get_adapter(adapter_name)
                    mapping = await adapter_manager._get_adapter_mapping(
                        conversation_uuid, adapter_name, db
                    )

                    logger.info(f"Adapter mapping result: mapping={mapping}")
                    if mapping:
                        logger.info(f"Adapter mapping: thread_id={mapping.thread_id}, metadata={mapping.adapter_metadata}")
                        logger.info(f"About to call send_message with: message={response[:50]}..., thread_id={mapping.thread_id}, metadata={mapping.adapter_metadata}")
                        # Send response through adapter
                        await adapter.send_message(
                            message=response,
                            conversation_id=conversation_uuid,
                            thread_id=mapping.thread_id,
                            metadata=mapping.adapter_metadata,
                        )
                        logger.info(f"Sent response to {adapter_name} for conversation {conversation_uuid}")
                    else:
                        logger.warning(f"No adapter mapping for {adapter_name}")
                except KeyError:
                    logger.error(f"Adapter '{adapter_name}' not found")
                except Exception as e:
                    logger.error(f"Error with adapter {adapter_name}: {e}", exc_info=True)
            else:
                logger.warning(f"No adapter info in conversation {conversation_uuid}")

    except Exception as e:
        logger.error(f"Error processing conversation: {e}", exc_info=True)


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


async def enqueue_conversation_processing(conversation_id: UUID) -> None:
    """Enqueue a conversation for background processing.

    Args:
        conversation_id: Conversation identifier
    """
    redis = await create_pool(
        RedisSettings.from_dsn(settings.arq_redis_url),
    )

    job = await redis.enqueue_job("process_conversation_job", str(conversation_id))
    if job:
        logger.info(f"Conversation {conversation_id} enqueued as job {job.job_id}")
    else:
        logger.warning(f"Failed to enqueue conversation {conversation_id}")


# ARQ Worker Configuration
class WorkerSettings:
    """Configuration for ARQ worker."""

    functions: ClassVar = [execute_task_job, process_conversation_job]
    redis_settings: ClassVar = RedisSettings.from_dsn(settings.arq_redis_url)
    max_jobs: ClassVar = settings.max_worker_jobs
    job_timeout: ClassVar = 600  # 10 minutes
    keep_result: ClassVar = 3600  # Keep results for 1 hour
