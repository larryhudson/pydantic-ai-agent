# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Agent Platform is an **architectural design experiment** exploring how to structure an application for building and deploying AI agents using Pydantic AI. The design explores multiple interaction patterns (chatbots, sidekicks, delegation, scheduled tasks, triggered tasks) with built-in conversation management, task scheduling, and background job execution.

**Priority:** This project prioritizes *architectural clarity and design exploration* over production-readiness. As new requirements emerge, we make changes that improve the design understanding and structure.

**Tech Stack:**
- FastAPI + Uvicorn for HTTP API
- SQLAlchemy (async) + PostgreSQL for persistence
- Redis for caching and async jobs (via arq)
- APScheduler for scheduled tasks
- Pydantic AI for agent execution
- uv for dependency management

## Development Commands

Use these commands for common development tasks:

```bash
# Start development server (FastAPI with hot-reload)
make dev

# View development server logs
make dev-logs

# Stop development server
make stop-dev

# Lint Python files with ruff
make lint

# Format Python files with ruff
make format

# Type check with ty
make type-check

# Lint and format a single file
make lint-file FILE=path/to/file.py
```

## Architecture

### High-Level Structure

The application follows a layered architecture:

1. **API Layer** (`app/api/`) - FastAPI routers for HTTP endpoints
   - `conversations.py` - Endpoints for creating/managing conversation threads
   - `tasks.py` - Endpoints for background task management

2. **Service Layer** (`app/services/`) - Core business logic
   - `agent_executor.py` - Executes Pydantic AI agents with two patterns:
     - `execute_sync()`: Streaming execution for chatbot/sidekick (immediate response)
     - `execute_async()`: Non-blocking execution for delegation/scheduled/triggered tasks
   - `conversation_manager.py` - Manages conversation threads and message history
   - `task_manager.py` - Task lifecycle and status tracking
   - `notification_service.py` - Sends notifications via email, Slack, webhooks

3. **Database Layer** (`app/database/`)
   - `models.py` - SQLAlchemy ORM models (ConversationDB, MessageDB, TaskDB)
   - `connection.py` - Async database connection and session management
   - Alembic migrations in `migrations/` (if present)

4. **Domain Models** (`app/models/domain.py`)
   - Pydantic models for type safety
   - Enums: `ConversationStatus`, `MessageRole`, `TaskType`, `TaskStatus`, `NotificationChannel`

5. **Workers** (`app/workers/`)
   - `scheduler.py` - APScheduler integration for recurring and delayed tasks
   - `task_worker.py` - Background job execution (likely using arq)

6. **Configuration** (`app/config.py`)
   - Settings class using Pydantic settings
   - Loads from environment variables (.env file)
   - Configurable: database, Redis, API keys, SMTP, notifications

### Key Design Patterns

**Agent Execution Patterns:**
- **Chatbot/Sidekick**: Synchronous streaming via `execute_sync()` - user waits for response
- **Delegation/Scheduled/Triggered**: Asynchronous via `execute_async()` - returns immediately, processes in background
- Both patterns maintain full conversation history for context

**Message Flow:**
1. User message added to conversation via ConversationManager
2. Previous messages loaded for context
3. Agent executes with message history
4. Response saved to conversation
5. For async patterns, execution happens in background worker

**Database Strategy:**
- Conversation threads track interaction pattern type and context
- Messages include role (user/assistant/system) and optional tool call metadata
- Tasks linked to conversations for tracking delegation/scheduled/triggered execution

## Configuration

All settings are managed via environment variables in `.env`:

```env
# Application
APP_NAME=AI Agent Platform
APP_VERSION=0.1.0
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_agent_platform

# Redis
REDIS_URL=redis://localhost:6379

# AI Models
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
DEFAULT_MODEL=openai:gpt-4

# SMTP (for email notifications)
SMTP_HOST=localhost
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@aiagent.platform

# Notifications
SLACK_WEBHOOK_URL=

# Background jobs
ARQ_REDIS_URL=redis://localhost:6379
MAX_WORKER_JOBS=10

# Scheduler
SCHEDULER_TIMEZONE=UTC
```

## Design Philosophy

When working on this codebase, prioritize:

1. **Architectural Clarity** - Make design decisions explicit and understandable. Code should communicate the architecture.
2. **Exploration Over Completion** - It's okay to have incomplete implementations if they clarify the design space.
3. **Design Evolution** - As requirements emerge, be willing to refactor and reshape the architecture. The goal is to find the right structure, not preserve existing code.
4. **Understanding** - Before adding features, ensure the existing design is well understood. Add code that tests understanding.

When proposing changes, consider:
- Does this improve the architectural clarity?
- Does this help us understand the problem space better?
- Does this reveal new design trade-offs?

## Common Development Tasks

### Exploring an Interaction Pattern or Use Case

1. Identify what architectural patterns or design decisions the use case reveals
2. Create/modify API endpoint in `app/api/` to explore the pattern
3. Inject appropriate services and observe how they fit together
4. Refactor services if the pattern reveals gaps or awkward boundaries
5. Document what the pattern reveals about the design

### Adding a New Scheduled Task

1. Define task logic in a service class
2. Register in `app/workers/scheduler.py` using APScheduler
3. Use `load_scheduled_tasks()` in app startup (main.py)

### Adding a Database Model

1. Create SQLAlchemy model in `app/database/models.py`
2. Create corresponding Pydantic domain model in `app/models/domain.py`
3. Create database migration with Alembic
4. Create service class in `app/services/` for CRUD operations

### Executing an Agent with Custom Logic

Inject `AgentExecutor` into your endpoint/service:
```python
executor = AgentExecutor(agent, db_session)

# For immediate streaming response
async for chunk in executor.execute_sync(conversation_id, user_message):
    yield chunk

# For background execution
result = await executor.execute_async(conversation_id, prompt)
```

## Testing

Pytest is configured as a dev dependency. Common patterns:

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app

# Run specific test file
uv run pytest tests/test_services.py

# Run with verbose output
uv run pytest -v
```

## Code Quality

Post-edit hooks automatically run on every file modification:
- **ruff check**: Linting with flake8, isort, pyupgrade rules
- **ruff format**: Code formatting
- **ty check**: Type checking

Manually run via:
```bash
make lint
make format
make type-check
```

## Linting Configuration

Ruff is configured in `pyproject.toml`:
- Line length: 100 characters
- Python 3.12+ target
- Selected rules: E, W, F, I, B, UP, C4, RUF
- Ignored: E501 (line too long), B008 (FastAPI Depends pattern)
- First-party module: `app`

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app setup with lifespan, routers, CORS |
| `app/config.py` | Settings class and environment configuration |
| `app/services/agent_executor.py` | Core agent execution with sync/async patterns |
| `app/services/conversation_manager.py` | Conversation and message persistence |
| `app/database/models.py` | SQLAlchemy ORM models |
| `app/models/domain.py` | Pydantic domain models and enums |
| `pyproject.toml` | Dependencies and tool configuration |
| `Makefile` | Development commands |

## Database Setup

Requires PostgreSQL and Redis running. Initial setup:

```bash
# Ensure database and Redis are running
createdb ai_agent_platform  # or use your preferred method

# Run migrations (if Alembic migrations exist)
uv run alembic upgrade head

# Start the application
make dev
```

## Debugging

- Enable `DEBUG=true` and `DATABASE_ECHO=true` in `.env` for detailed logging
- Use FastAPI interactive docs at http://localhost:8000/docs
- Check logs with `make dev-logs`
- Database models auto-generate SQLAlchemy logs when echo is enabled
