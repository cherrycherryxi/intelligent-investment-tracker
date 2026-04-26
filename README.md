# Intelligent Investment Tracker

Day1 foundation for an intelligent foreign exchange and bond investment tracker built around a FastAPI API layer, MCP-style tools, and AI-assisted analysis.

## Current Scope

This repository currently provides the development baseline for:

- project structure and package layout
- environment-driven settings management
- structured JSON logging
- SQLAlchemy ORM models and session utilities
- Alembic migration scaffolding and initial schema
- CI checks for linting and tests

Day1 does not yet implement OCR, exchange-rate crawling, natural-language parsing, or AI advice generation.

## Architecture Overview

The project is organized in four layers:

1. API layer: future FastAPI endpoints and request handling
2. Orchestration layer: future task planning and tool coordination
3. Tool layer: future MCP-compatible OCR, parsing, pricing, and advice tools
4. Data layer: settings, logging, persistence, and migrations

## Tech Stack

- Python 3.9+
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic Settings
- Pytest
- Ruff

## Repository Layout

```text
src/investment_tracker/
  api/
  orchestration/
  mcp_tools/
  skills/
  data/
  utils/
tests/
config/
alembic/
```

## Local Development

### 1. Create the environment

```bash
uv sync
```

If your environment cannot reach PyPI, install the dependencies later when network access is available.

### 2. Configure environment variables

Copy `.env.example` into `.env` and adjust values as needed.

### 3. Run tests

```bash
uv run pytest
```

### 4. Run linting

```bash
uv run ruff check .
```

## Database Migrations

Upgrade to the latest schema:

```bash
uv run python -m alembic upgrade head
```

Create a new migration later:

```bash
uv run python -m alembic revision -m "describe change"
```

Initialize the database directly from ORM metadata:

```bash
uv run python scripts/init_db.py
```

## Day 2-7 Roadmap

- Day2: MCP tool abstractions and core tool implementations
- Day3: AI model client and investment advice engine
- Day4: reusable skills and evaluation harness
- Day5: API endpoints and orchestration workflows
- Day6: dashboard, export, and portfolio analysis
- Day7: hardening, demos, and documentation polish
