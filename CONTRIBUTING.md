# Contributing to agents_protocol

First off, thank you for considering contributing to `agents_protocol`. It's people like you that make this tool great!

## Development Setup

1. **Fork and Clone** the repository to your local machine.
2. **Install Dependencies** including development tools:
   ```bash
   pip install -e ".[dev]"
   ```
3. **Install Pre-commit Hooks** to automatically run black, flake8, and mypy on every commit:
   ```bash
   pre-commit install
   ```

## Workflow

1. Create a new branch for your feature or bugfix (`git checkout -b feature/my-new-feature`).
2. Make your modifications.
3. Ensure to write tests for your code in the `tests/` directory.
4. Run the entire test suite via `pytest`:
   ```bash
   pytest --cov=agents_protocol tests/
   ```
5. Ensure your code passes all linting and type-checking (handled by pre-commit dynamically, or run it manually):
   ```bash
   pre-commit run --all-files
   ```
6. Commit your changes.
7. Push to your fork and submit a Pull Request.

## Coding Standards

- **Formatting:** We use `black` for auto-formatting.
- **Linting:** We use `flake8`.
- **Type Hinting:** All code must be strictly typed and pass `mypy`.
- **AsyncIO:** This protocol relies heavily on native Python `asyncio`. Avoid blocking I/O calls without using local executors.
