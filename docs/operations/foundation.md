# API Foundation Operations

## Local ports

- API host port: `8010` → container port `8000`.
- PostgreSQL host port: `5432`.
- The host port avoids conflict with the existing `huella-api` service on `8000`.

## Local startup

```bash
cp .env.example .env
docker compose up -d --build
curl -fsS http://localhost:8010/api/v1/health/live
curl -fsS http://localhost:8010/api/v1/health/ready
```

The API container applies Alembic migrations before starting Uvicorn in the development Compose
stack. Production migrations MUST be reviewed and run as an explicit release step before traffic
is switched.

## Resource baseline

- One Uvicorn worker.
- SQLAlchemy pool size 5, max overflow 5, five-second pool timeout.
- No Redis, queue, resident worker, or image processing service.
- Target API RSS below 384MB under foundation workload; Uribap service budget remains below 1GB
  excluding shared identity infrastructure.
- Local Docker baseline on 2026-09-08: API 215.3MiB, PostgreSQL 49.27MiB, Web 56.02MiB.
  These are development observations, not production capacity guarantees.

## Health semantics

- `/api/v1/health/live` checks process/routing only.
- `/api/v1/health/ready` requires a reachable database with `alembic_version` present.
- Health output never contains connection strings, credentials, access tokens, or stack traces.

## Validation

```bash
uv run ruff check .
uv run pyright
uv run pytest
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```
