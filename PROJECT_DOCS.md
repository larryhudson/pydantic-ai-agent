# AI Agent Platform

A unified architecture for supporting multiple AI agent interaction patterns using FastAPI and Pydantic AI.

## Overview

This platform supports six different AI agent interaction patterns:

1. **Chatbot** - Synchronous, real-time conversational interactions
2. **Sidekick** - Context-aware assistant integrated with application state
3. **Delegation** - One-time background tasks
4. **Scheduled Tasks** - Recurring tasks on a schedule
5. **Event-Triggered Tasks** - Tasks triggered by webhooks/events
6. **Deep Research** - Long-running research tasks

## Architecture

The platform uses a unified conversation model where all patterns are variations of the same fundamental concept—an agent conversation with different triggering mechanisms, execution contexts, and notification strategies.

### Core Components

- **FastAPI** - Web framework for API endpoints
- **Pydantic AI** - Agent framework for executing LLM interactions
- **PostgreSQL** - Primary database for conversation and task storage
- **Redis** - Caching and job queue
- **SQLAlchemy** - Async ORM for database operations
- **Alembic** - Database migrations
- **ARQ** - Background job queue for async task execution
- **APScheduler** - Task scheduler for recurring jobs

## Project Structure

```
app/
├── api/                    # API endpoints
│   ├── conversations.py    # Conversation management endpoints
│   └── tasks.py           # Task management endpoints
├── database/              # Database layer
│   ├── models.py         # SQLAlchemy ORM models
│   └── connection.py     # Database connection and session management
├── models/                # Domain models
│   └── domain.py         # Pydantic domain models
├── services/              # Business logic layer
│   ├── agent_executor.py      # Executes Pydantic AI agents
│   ├── conversation_manager.py # Manages conversation threads
│   ├── task_manager.py        # Manages task lifecycle
│   └── notification_service.py # Handles notifications
├── workers/               # Background processing
│   ├── task_worker.py    # ARQ worker for background tasks
│   └── scheduler.py      # APScheduler for scheduled tasks
├── config.py             # Application configuration
└── main.py               # FastAPI application entry point

alembic/                   # Database migrations
```

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Redis 6+
- UV package manager (recommended)

### Installation

1. Clone the repository and install dependencies:

```bash
uv sync
```

2. Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Set up the database:

```bash
# Make sure PostgreSQL is running and create the database
createdb ai_agent_platform

# Run migrations
uv run alembic upgrade head
```

### Configuration

Key environment variables in `.env`:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_platform

# Redis
REDIS_URL=redis://localhost:6379
ARQ_REDIS_URL=redis://localhost:6379

# AI Model (choose one or both)
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
DEFAULT_MODEL=openai:gpt-4

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com

# Slack (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Running the Application

### Start the API Server

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation: `http://localhost:8000/docs`

### Start the Background Worker (for delegated tasks)

In a separate terminal:

```bash
uv run arq app.workers.task_worker.WorkerSettings
```

### Database Migrations

Create a new migration:

```bash
uv run alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

## Usage Examples

### 1. Chatbot Pattern (Synchronous Chat)

```python
import httpx

# Create a conversation
response = httpx.post("http://localhost:8000/conversations", json={
    "pattern_type": "chatbot",
    "context_data": {}
})
conversation = response.json()
conversation_id = conversation["id"]

# Send a message
response = httpx.post(
    f"http://localhost:8000/conversations/{conversation_id}/messages",
    json={
        "message": "What is the capital of France?",
        "stream": False
    }
)
print(response.json())
```

### 2. Delegation Pattern (Background Task)

```python
import httpx

# Create a delegated task
response = httpx.post("http://localhost:8000/tasks", json={
    "task_type": "delegation",
    "prompt": "Research the latest trends in AI and write a summary",
    "notification_config": {
        "channels": ["email"],
        "email_address": "user@example.com"
    }
})
task = response.json()
print(f"Task created: {task['id']}")

# Check task status
response = httpx.get(f"http://localhost:8000/tasks/{task['id']}")
print(response.json())
```

### 3. Scheduled Task Pattern

```python
import httpx

# Create a scheduled task (daily at 9 AM)
response = httpx.post("http://localhost:8000/tasks", json={
    "task_type": "scheduled",
    "prompt": "Generate a daily report of system metrics",
    "schedule_expression": "0 9 * * *",  # Cron: every day at 9 AM
    "notification_config": {
        "channels": ["slack"],
        "slack_webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK"
    }
})
task = response.json()
print(f"Scheduled task created: {task['id']}")
```

### 4. Event-Triggered Pattern

```python
import httpx

# Create a triggered task
response = httpx.post("http://localhost:8000/tasks", json={
    "task_type": "triggered",
    "prompt": "Process incoming webhook data and send analysis",
    "trigger_config": {},
    "notification_config": {
        "channels": ["email"],
        "email_address": "user@example.com"
    }
})
task = response.json()
task_id = task["id"]

# Webhook endpoint will be: http://localhost:8000/tasks/webhooks/{task_id}
print(f"Webhook URL: http://localhost:8000/tasks/webhooks/{task_id}")

# Trigger the task via webhook
response = httpx.post(
    f"http://localhost:8000/tasks/webhooks/{task_id}",
    json={"event": "data_received", "data": "..."}
)
```

## API Endpoints

### Conversations

- `POST /conversations` - Create a new conversation
- `GET /conversations/{id}` - Get conversation details
- `GET /conversations/{id}/messages` - Get conversation messages
- `POST /conversations/{id}/messages` - Send a message (supports streaming)
- `POST /conversations/{id}/continue` - Continue a conversation thread

### Tasks

- `POST /tasks` - Create a new task
- `GET /tasks` - List all tasks (with filters)
- `GET /tasks/{id}` - Get task details
- `PATCH /tasks/{id}` - Update task configuration
- `DELETE /tasks/{id}` - Delete a task
- `POST /tasks/{id}/execute` - Manually trigger task execution
- `POST /tasks/{id}/disable` - Disable a task
- `POST /tasks/webhooks/{id}` - Webhook endpoint for triggered tasks

## Development

### Run Tests

```bash
uv run pytest
```

### Linting and Formatting

```bash
uv run ruff check .
uv run ruff format .
```

### Type Checking

```bash
uv run pyright
```

## Key Design Decisions

1. **Unified Conversation Model** - All patterns use the same conversation and message models
2. **Separation of Concerns** - Clear separation between API, services, and data layers
3. **Async by Default** - All database and external operations are async
4. **Flexible Execution** - Same agent executor works for both sync and async patterns
5. **Notification Abstraction** - Single service handles all notification channels

## Next Steps

Future enhancements to consider:

- [ ] Multi-agent coordination
- [ ] Task dependencies (chain tasks together)
- [ ] Rich context sources (Google Drive, Slack, etc.)
- [ ] Agent marketplace with custom tools
- [ ] Advanced scheduling triggers
- [ ] Conversation branching
- [ ] Audit logging
- [ ] Rate limiting
- [ ] Cost tracking

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
