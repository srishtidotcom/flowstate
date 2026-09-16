# Testing Flowstate

Run every command from the repository root. Automated tests are isolated from
Ollama, Google Calendar, OpenClaw, n8n, and the public internet.

## Environment setup

Flowstate uses the repository's single `.venv` environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

Do not create or use a second `venv/` environment. Dependencies required by
runtime or tests must be recorded in `requirements.txt`.

## Automated tests

These commands do not require external services:

```bash
# Discover the entire suite
.venv/bin/python -m pytest --collect-only -q

# Fast deterministic unit suite
.venv/bin/python -m pytest tests/unit -q

# Integration suite with isolated database/queue/vector substitutes
.venv/bin/python -m pytest tests/integration -v --tb=short

# Required Phase 1 regression command
.venv/bin/python -m pytest tests/unit tests/integration -v --tb=short
```

The repository root is configured in `pyproject.toml`; do not set `PYTHONPATH`
or add path manipulation to tests.

## Local infrastructure verification

The production adapters can be checked separately with local containers:

```bash
docker compose -f docker/docker-compose.yml up -d postgres chromadb redis
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
.venv/bin/python -m alembic history
docker compose -f docker/docker-compose.yml ps
```

Infrastructure verification is not part of the hermetic automated test suite.

## Optional Ollama smoke test

Ollama tests are explicitly marked and excluded unless requested. Start the
service and model before running them:

```bash
ollama serve
ollama pull mistral
.venv/bin/python -m pytest -m ollama -v
```

Never run the optional smoke test as part of the default unit or integration
suite. Automated extraction tests mock the HTTP boundary and must pass while
Ollama is stopped.
