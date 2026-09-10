# Implementation Plan: API Foundation

**Branch**: `001-api-foundation` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification for the Dockerized FastAPI backend foundation.

## Summary

Create a small, Dockerized FastAPI service with a reproducible PostgreSQL migration boundary,
separate liveness/readiness health, structured safe errors, a generated OpenAPI contract, and
layered source structure ready for Uribap's deterministic domain services. This feature does
not implement authentication, household records, recipes, inventory lots, or forecasting.

The implementation uses CLI scaffolding and pinned releases. The backend runs with Python 3.14,
FastAPI, SQLAlchemy 2, Alembic, psycopg 3, Pydantic settings, Uvicorn, Ruff, Pyright, pytest,
pytest-asyncio, and HTTPX. PostgreSQL 18 is the development database image; the production
Coolify database remains independently managed.

## Technical Context

**Language/Version**: Python 3.14.x

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy 2, psycopg 3,
Alembic, Ruff, Pyright, pytest, pytest-asyncio, HTTPX

**Storage**: PostgreSQL 18 for development and integration tests; migration boundary only in this feature

**Testing**: pytest unit/integration/API layers, HTTPX ASGI tests, PostgreSQL integration service,
OpenAPI snapshot comparison

**Target Platform**: Linux Docker container on Coolify; local Docker Compose development

**Project Type**: Layered web service / REST API

**Performance Goals**: liveness p95 under 500ms; readiness response under 2s when the database
is unavailable; one-worker development/production baseline; API service target below 384MB RSS
under foundation workload and below the agreed 1GB Uribap service budget

**Constraints**: no secrets in tracked files; no resident queue/cache/worker; small DB pool;
Decimal-safe contract; structured redacted logs; public repository; `main` branch

**Scale/Scope**: foundation for a household application with small initial traffic, up to 14-day
projection reads per household, and independent API/Web repositories

## Constitution Check

- **Domain correctness**: PASS. No domain calculation or inventory mutation is implemented here;
  the layer boundaries explicitly reserve those behaviors for later pure services.
- **Determinism and test-first**: PASS. Health, configuration, migration, error, and contract
  behavior have unit/integration/API acceptance coverage before feature implementation.
- **Tenant/security**: PASS. The auth dependency boundary exists without storing passwords; logs
  redact secrets and no tenant data is introduced in this foundation.
- **Contract-first**: PASS. The API contract and Problem Details shape are generated and checked
  from the service source.
- **Resource-aware simplicity**: PASS. No cache/queue/worker is introduced; the container uses a
  bounded pool and one-worker baseline.
- **Auditable operations**: PASS. Alembic migration workflow, health checks, lockfiles, Docker
  checks, and secret scanning are foundation gates.

## Model Assignment

- **Primary**: `gpt-5-6-luna-high` for architecture and implementation plan reasoning.
- **Implementation**: `gpt-5-6-sol-high` for multi-file foundation code and migrations.
- **Reviewer**: `gpt-5-6-terra-high` for security, configuration, error and migration review.
- **Artifact analyst**: `glm-5-3-max` for `speckit-analyze` and long-context consistency.
- **Routine fixer**: `swe-2-high` for bounded lint/type/test corrections; use `swe-2-max` for bounded multi-file fixes.
- **Escalation**: `gpt-5-6-terra-max` only after explicit review shows unresolved critical risk;
  `kimi-k3-max` only for unusually large cross-repository artifact review.

## Project Structure

### Documentation (this feature)

```text
specs/001-api-foundation/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── foundation-api.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/uribap_api/
├── __init__.py
├── main.py
├── config.py
├── api/
│   ├── dependencies.py
│   ├── errors.py
│   ├── health.py
│   └── router.py
├── application/
│   └── health_service.py
├── domain/
│   └── shared/
│       ├── errors.py
│       └── result.py
└── infrastructure/
    ├── database.py
    └── logging.py

migrations/
├── env.py
└── versions/

tests/
├── unit/
├── integration/
└── api/

openapi/
└── openapi.json

Dockerfile
compose.yml
.dockerignore
.env.example
pyproject.toml
uv.lock
alembic.ini
```

**Structure Decision**: Use a single `src/` package with explicit API/application/domain/
infrastructure boundaries and separate tests by execution layer. Domain folders are intentionally
minimal until the later ingredient/inventory specs add their entities and pure engines.

## Implementation Phases

### Phase 0 — Research and decisions

- Validate release support for Python 3.14, PostgreSQL 18, FastAPI, SQLAlchemy, psycopg and Alembic.
- Confirm the OpenAPI export/check approach and Problem Details shape.
- Confirm Docker healthcheck and memory/pool defaults.

### Phase 1 — Foundation design

- Create configuration, application factory, dependency wiring, health endpoints, error envelope,
  database engine/session boundary, logging redaction, migration baseline, Docker files and tests.
- Generate the canonical OpenAPI JSON and add deterministic snapshot validation.
- Re-check every constitution gate and the API contract before tasks are generated.

## Complexity Tracking

No constitution violations. No additional service, cache, queue, repository abstraction, or worker
is introduced in this foundation feature.
