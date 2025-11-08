# Claude Code Dev Starter Template

A production-ready Python template for setting up new projects optimized for working with [Claude Code](https://docs.claude.com/en/docs/claude-code/). This template includes development tools, linting hooks, CI/CD pipelines, and Claude Code integrations to streamline your development workflow.

## What's Included

### Development Setup

- **Makefile**: Convenient commands for managing your Python development environment
  - `make dev`: Start FastAPI development server using hivemind with process management
  - `make dev-logs`: View and tail development logs (with ANSI codes stripped for readability)
  - `make lint`: Lint Python files with ruff
  - `make format`: Format Python files with ruff
  - `make type-check`: Type check Python files with ty
  - `make stop-dev`: Stop the running development server

- **Procfile**: Configuration file for hivemind to manage development processes
  - FastAPI development server with auto-reload using `uv run fastapi dev`
  - Can be extended with additional processes

- **pyproject.toml**: Python project configuration
  - FastAPI and Uvicorn dependencies
  - Development dependencies (ruff, ty, pyyaml)
  - Ruff linting and formatting configuration

- **uv**: Fast Python package manager for dependency management
  - Replaces pip/venv for faster, more reliable dependency resolution

### Claude Code Integration

- **Hook Configuration** (`.claude/settings.json`): Registers hooks with Claude Code
  - PostToolUse hook runs on Write/Edit tools with 30-second timeout
  - SessionStart hook runs on session initialization with 60-second timeout

- **PostToolUse Hook** (`.claude/hooks/post-tool-use.py`): Python script that automatically runs checks after Claude modifies files
  - Reads configuration from `.post-claude-edit-config.yaml`
  - Matches modified files against glob patterns
  - Runs configured commands with proper substitution (`{file}`, `{dir}`)
  - Returns structured JSON feedback to Claude Code
  - Automatically lints, formats, and type-checks Python files after edits

- **Post-Claude-Edit Configuration** (`.post-claude-edit-config.yaml`): Defines what checks run after edits
  - Pattern-based file matching (e.g., `*.py`)
  - Flexible command configuration for Python tooling
  - Enable/disable checks without removing them
  - Includes ruff linting, formatting, and ty type-checking

- **SessionStart Hook** (`.claude/hooks/session-start.sh`): Runs when a Claude Code session starts
  - Checks for required development tools (hivemind, jq, uv, python)
  - Installs Python dependencies if needed
  - Provides helpful context about available commands

### Code Quality

- **.pre-commit-config.yaml**: Pre-commit hooks for automated code quality checks
  - Trailing whitespace removal
  - End-of-file fixing
  - YAML validation
  - Large file detection
  - JSON validation
  - Merge conflict detection
  - Optional: ESLint configuration (commented out for flexibility)

### CI/CD

- **.github/workflows/ci.yaml**: GitHub Actions workflow for automated testing and linting
  - Runs on push to main/develop branches and pull requests
  - Lint job: Checks Python code style with ruff
  - Type-check job: Validates Python types with ty
  - Python 3.12+ environment with uv caching

## Getting Started

### 1. Installation

```bash
# Install uv (Python package manager)
# On macOS
brew install uv

# On Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install hivemind (for process management)
# On macOS
brew install hivemind

# On Linux
# Follow instructions at https://github.com/DarthSim/hivemind

# Install pre-commit framework
pip install pre-commit

# Set up pre-commit hooks
pre-commit install

# Install Python dependencies via uv
uv sync
```

### 2. Configure Your Project

1. Update `pyproject.toml` with your project's dependencies:
   ```toml
   [project]
   name = "my-project"
   dependencies = [
       "fastapi[standard]>=0.120.0",
       "uvicorn[standard]>=0.38.0",
       "sqlalchemy>=2.0.0",  # Add as needed
   ]

   [dependency-groups]
   dev = [
       "pytest>=7.0.0",
       "pytest-cov>=4.0.0",
   ]
   ```

2. Update `Procfile` with your project's development commands:
   ```
   web: uv run fastapi dev app/main.py
   tests: uv run pytest --watch
   ```

3. Update `.post-claude-edit-config.yaml` with checks you want to run:
   ```yaml
   checks:
     - name: lint-python
       patterns: ['*.py']
       command: 'uv run ruff check --fix {file}'
       enabled: true
     - name: my-custom-check
       patterns: ['app/**/*.py']
       command: 'uv run pytest {file}'
       enabled: false
   ```
   - Add custom checks for your project
   - Use `{file}` placeholder for the modified file path
   - Set `enabled: false` to disable checks temporarily

4. Update `.pre-commit-config.yaml` with hooks relevant to your project:
   - Add additional hooks for Python linting beyond ruff if desired

5. Update `.github/workflows/ci.yaml` with your actual test commands:
   - Ensure `uv run ruff check`, `uv run ty check`, and `uv run pytest` work
   - Or adjust the commands to match your project

### 3. Claude Code Configuration

The Claude Code hooks are already configured in `.claude/settings.json`. The configuration includes:

- **PostToolUse Hook**: Automatically runs checks after Write/Edit tools
  - Triggered when Claude modifies files
  - Runs matching checks from `.post-claude-edit-config.yaml`
  - 30-second timeout per command

- **SessionStart Hook**: Prepares development environment
  - Checks for required tools
  - Installs dependencies
  - Provides context about available commands
  - 60-second timeout

No additional configuration needed—the hooks will run automatically in Claude Code!

## Usage Examples

### Starting Development

```bash
# Start all processes defined in Procfile
make dev

# In another terminal, view live logs
make dev-logs

# When done, stop the server
make stop-dev
```

### Working with Claude Code

1. **Edit a file**: Claude modifies `app/main.py`
2. **Automatic formatting**: The PostToolUse hook runs linting, formatting, and type-checking
3. **Result**: File is automatically linted, formatted, and type-checked

### Manual Linting and Type Checking

```bash
# Lint all Python files
make lint

# Format all Python files
make format

# Type check all Python files
make type-check

# Or use the tools directly
uv run ruff check --fix .
uv run ruff format .
uv run ty check .
```

### Running Tests

```bash
# Run tests with pytest
uv run pytest

# Run tests with coverage
uv run pytest --cov=app
```

### Running Pre-commit Checks

```bash
# Run all pre-commit checks on staged files
pre-commit run

# Run all pre-commit checks on all files
pre-commit run --all-files

# Update hook versions
pre-commit autoupdate
```

## File Structure

```
.
├── .claude/
│   ├── settings.json              # Claude Code hook configuration
│   └── hooks/
│       ├── post-tool-use.py       # Python script for post-edit checks
│       └── session-start.sh        # Bash script for session setup
├── .github/
│   └── workflows/
│       └── ci.yaml                # GitHub Actions CI/CD pipeline
├── app/
│   ├── __init__.py               # App package
│   └── main.py                    # FastAPI application entry point
├── tests/                         # Test directory (add pytest tests here)
├── .post-claude-edit-config.yaml   # Post-edit checks configuration
├── .pre-commit-config.yaml         # Pre-commit hook configuration
├── Makefile                        # Development commands
├── Procfile                        # Process definitions for hivemind
├── pyproject.toml                  # Python project configuration and dependencies
├── uv.lock                         # Locked dependencies (managed by uv)
└── README.md                       # This file
```

## Customization

### Adding Post-Claude-Edit Checks

Edit `.post-claude-edit-config.yaml` to add or modify checks:

```yaml
checks:
  - name: lint-python
    patterns: ['*.py']
    command: 'uv run ruff check --fix {file}'
    enabled: true

  - name: format-python
    patterns: ['*.py']
    command: 'uv run ruff format {file}'
    enabled: true

  - name: test-file
    patterns: ['tests/**/*.py']
    command: 'uv run pytest {file}'
    enabled: false  # Disabled for now
```

- **patterns**: Glob patterns to match file paths (fnmatch style)
- **command**: Command to execute (use `{file}` for file path, `{dir}` for directory)
- **enabled**: Toggle without deleting the check

### Adding Dependencies

Edit `pyproject.toml` to add new dependencies:

```toml
[project]
dependencies = [
    "fastapi[standard]>=0.120.0",
    "sqlalchemy>=2.0.0",  # Add your dependency
]

[dependency-groups]
dev = [
    "pytest>=7.0.0",
    "black>=23.0.0",  # Add dev tools
]
```

Then run `uv sync` to update your environment.

### Adding More Make Targets

Edit `Makefile` to add custom targets:

```makefile
test:
	uv run pytest

deploy:
	uv run fastapi run app/main.py
```

### Adding More Processes

Edit `Procfile` to add or remove processes:

```procfile
web: uv run fastapi dev app/main.py
api: uv run python scripts/background_worker.py
tests: uv run pytest --watch
```

### Extending Pre-commit Hooks

Uncomment or add hooks to `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/your-org/custom-hooks
  rev: v1.0.0
  hooks:
    - id: custom-check
```

### Customizing Hook Timeouts

Edit `.claude/settings.json` to adjust hook timeouts:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-tool-use.py",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

Increase timeout if your checks take longer to run.

## Troubleshooting

### Dev server already running

If you see "Dev server is already running", you can either:
- Run `make stop-dev` to stop the existing server
- Check the `.dev.pid` file to see the PID

### Hooks not executing

Ensure hooks are executable:
```bash
chmod +x .claude/hooks/*.sh
```

### Pre-commit issues

Update pre-commit and hooks:
```bash
pre-commit clean
pre-commit autoupdate
pre-commit run --all-files
```

## Learn More

- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code/)
- [Hivemind Documentation](https://github.com/DarthSim/hivemind)
- [Pre-commit Framework](https://pre-commit.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## License

This template is provided as-is for use with Claude Code projects.
