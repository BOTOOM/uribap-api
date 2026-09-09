# Quickstart: API Foundation

## Prerequisites

- Docker Engine and Docker Compose
- Python 3.14.x
- `uv`
- Git

## Start

```bash
cp .env.example .env
uv sync --locked
docker compose up --build -d
uv run alembic upgrade head
```

## Validate health

```bash
curl -fsS http://localhost:8000/api/v1/health/live
curl -fsS http://localhost:8000/api/v1/health/ready
```

Expected: liveness returns HTTP 200 without requiring a database; readiness returns HTTP 200
only after PostgreSQL is reachable and at the migration head.

## Validate tests and contract

```bash
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/integration
uv run pytest tests/api
uv run python -m uribap_api.tools.export_openapi --check
```

## Failure scenarios

1. Stop PostgreSQL and call readiness: expect HTTP 503 with a safe dependency code.
2. Remove a required environment variable and start the API: expect a startup validation error
   without printing the secret value.
3. Send malformed JSON: expect the documented Problem Details shape.
4. Run contract export twice: expect no git diff.

## Cleanup

```bash
docker compose down
```

Do not remove volumes as part of the normal quickstart; data-destroying commands require an
explicit operator decision.
