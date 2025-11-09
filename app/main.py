"""Main FastAPI application for AI Agent Platform."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.conversations import router as conversations_router
from app.api.tasks import router as tasks_router
from app.config import get_settings
from app.database import close_db, init_db
from app.workers.scheduler import load_scheduled_tasks, start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    # Startup
    logger.info("Starting AI Agent Platform")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    start_scheduler()
    logger.info("Scheduler started")

    # Load scheduled tasks
    await load_scheduled_tasks()
    logger.info("Scheduled tasks loaded")

    yield

    # Shutdown
    logger.info("Shutting down AI Agent Platform")

    # Stop scheduler
    stop_scheduler()
    logger.info("Scheduler stopped")

    # Close database
    await close_db()
    logger.info("Database closed")


app = FastAPI(
    title=settings.app_name,
    description="AI Agent Platform supporting multiple interaction patterns with Pydantic AI",
    version=settings.app_version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(conversations_router)
app.include_router(tasks_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )
