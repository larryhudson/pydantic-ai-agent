# Procfile for use with hivemind
# This file defines the processes that should run during development

web: uv run fastapi dev app/main.py
worker: uv run arq app.workers.task_worker.WorkerSettings
