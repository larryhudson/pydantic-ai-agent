.PHONY: dev dev-logs lint-file lint format type-check help

PIDFILE := .dev.pid
DEV_LOG := dev.log

help:
	@echo "Available commands:"
	@echo "  make dev         - Start development server using hivemind"
	@echo "  make dev-logs    - View development logs"
	@echo "  make lint        - Lint Python files with ruff"
	@echo "  make format      - Format Python files with ruff"
	@echo "  make type-check  - Run type checking with ty"
	@echo "  make lint-file   - Lint and format a single file (usage: make lint-file FILE=path/to/file)"

dev:
	@hivemind Procfile

lint:
	@echo "Linting Python files with ruff..."
	@uv run ruff check .

format:
	@echo "Formatting Python files with ruff..."
	@uv run ruff format .

type-check:
	@echo "Type checking with ty..."
	@uv run ty check .

# Lint and format a single file
# Usage: make lint-file FILE=src/myfile.py
lint-file:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter required"; \
		echo "Usage: make lint-file FILE=path/to/file"; \
		exit 1; \
	fi
	@echo "Linting and formatting: $(FILE)"
	@uv run ruff check --fix $(FILE)
	@uv run ruff format $(FILE)
