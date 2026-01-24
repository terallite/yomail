# CLAUDE.md — yomail

## Purpose

A lightweight, fast, and highly robust system to extract body text from Japanese business emails.

**Production library with dev tooling** — Prioritize reliability, clean APIs for integration, graceful failure handling. Dev/training tools should be clear and straightforward.

## Before Starting Work

**Read DESIGN.md first** for understanding the system specification.

**Check PROGRESS.md** for current status and what's been completed.

**Check FEEDBACK.md** for open issues that need addressing.

## Tech Stack

- **Python**: 3.13+
- **Package manager**: uv
- **Type checker**: ty (strict)
- **Linter/formatter**: ruff
- **Testing**: pytest

## Commands

```bash
# Setup
uv sync

# Type check
uv run ty check

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Test
uv run pytest

# All checks (run after any implementation)
uv run ty check && uv run ruff check . && uv run pytest
```

**Sandbox note:** When running in Claude Code's sandbox, `uv run` may fail. Run tools directly from venv:

```bash
.venv/bin/ty check
.venv/bin/ruff check .
.venv/bin/pytest
.venv/bin/python -c "..."
```

## Coding Standards

### Types
- Strict typing everywhere. No `Any` unless unavoidable.
- Use modern syntax: `list[str]`, `dict[str, int]`, `X | None` (not `Optional[X]`).
- Dataclasses for all data structures.

### Style
- Clear, descriptive names. No single-letter variables except loop indices.
- Explicit is better than implicit.
- No monkey-patching.

### Error Handling
- Library functions should return structured results, not raise exceptions for expected failure cases.
- Use result types (e.g., `Result[T, E]` pattern or dataclass with success/error fields) for operations that can fail.
- Graceful degradation: partial results are better than no results.
- Log warnings for unexpected inputs, don't crash.

### Dependencies
- Minimal. Only add a dependency if reimplementing would be error-prone or substantial.
- Current expected deps: (none yet — likely will need email parsing utilities)

### Testing
- Light but solid. Cover key logic paths, not boilerplate.
- Tests should be easy to maintain — avoid brittle assertions on exact strings.
- Include tests with real Japanese email samples.

## Project Structure

```
yomail/
├── pyproject.toml
├── src/yomail/
│   └── __init__.py
└── tests/
```

## Workflow

- **Commit after each logical task** — Don't batch unrelated changes.
- **Read before modifying** — Never propose changes to code you haven't read.

## Progress Tracking

Project progress is tracked in **PROGRESS.md**. Update it when:
- Starting a work session (note what you're working on)
- Completing a milestone (check off items, add to session log)
- Making significant decisions (add to Notes section)

## Implementation Notes

DESIGN.md contains the original specification. This section documents key implementation deviations as they occur.

(To be updated as implementation progresses)

## Key Design Decisions

(To be documented as decisions are made)
