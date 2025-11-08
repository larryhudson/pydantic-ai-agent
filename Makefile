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
	@if [ -f $(PIDFILE) ] && kill -0 $$(cat $(PIDFILE)) 2>/dev/null; then \
		echo "Dev server is already running (PID: $$(cat $(PIDFILE)))"; \
		exit 1; \
	fi
	@echo $$ > $(PIDFILE)
	@echo "Starting development server with hivemind..."
	@hivemind Procfile > $(DEV_LOG) 2>&1 & \
	echo $$! >> $(PIDFILE)
	@echo "Dev server started. View logs with 'make dev-logs'"

dev-logs:
	@if [ -f $(DEV_LOG) ]; then \
		tail -n 50 $(DEV_LOG) | sed 's/\x1b\[[0-9;]*m//g'; \
	else \
		echo "Dev log file not found. Start dev server with 'make dev'"; \
	fi
	@echo ""
	@echo "Dev server status: " ; \
	if [ -f $(PIDFILE) ] && kill -0 $$(cat $(PIDFILE)) 2>/dev/null; then \
		echo "  running"; \
	else \
		echo "  stopped"; \
	fi

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

.PHONY: stop-dev
stop-dev:
	@if [ -f $(PIDFILE) ]; then \
		kill $$(cat $(PIDFILE)) 2>/dev/null || true; \
		rm -f $(PIDFILE); \
		echo "Dev server stopped"; \
	else \
		echo "No dev server running"; \
	fi
