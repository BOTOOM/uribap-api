# Research: API Foundation

## Decision 1: Python runtime and dependency workflow

- **Decision**: Use Python 3.14.x with `uv`, pinned lockfile, FastAPI, Uvicorn, Pydantic Settings,
  SQLAlchemy 2, psycopg 3, Alembic, Ruff, Pyright, pytest, pytest-asyncio and HTTPX.
- **Rationale**: The workspace already has Python 3.14 and `uv`; this keeps installation fast and
  reproducible while separating pure domain code from FastAPI. psycopg 3 avoids adding an extra
  database driver family.
- **Alternatives considered**: Python 3.13 for broader historical compatibility; Poetry/pip for
  dependency management; asyncpg for a second driver. Rejected for this foundation because the
  available environment and planned libraries support the current runtime, while `uv` is already
  installed and reduces tool duplication.

## Decision 2: PostgreSQL and migration boundary

- **Decision**: PostgreSQL 18 is the development/integration image; Alembic owns migrations and
  the API uses a least-privilege application role. The foundation migration creates no business
  tables beyond the migration bookkeeping required by Alembic.
- **Rationale**: Uribap needs relational transactions, numeric quantities, partial indexes and
  future row-locking. Keeping the first migration empty prevents domain assumptions from leaking
  into foundation.
- **Alternatives considered**: SQLite for local development, an embedded database, or a managed
  Supabase instance. Rejected because they do not exercise the PostgreSQL transaction behavior
  required by inventory and consumption.

## Decision 3: Health and error contract

- **Decision**: `GET /health/live` checks process availability only; `GET /health/ready` checks
  required database readiness. Invalid requests and operational failures use an RFC 9457-style
  Problem Details envelope with a correlation id.
- **Rationale**: Coolify needs a cheap liveness probe and a dependency-aware readiness probe; a
  stable error shape lets Web handle failure states without parsing framework-specific messages.
- **Alternatives considered**: One combined `/health` endpoint and ad-hoc JSON errors. Rejected
  because they blur restart/readiness behavior and create contract drift.

## Decision 4: Layer boundaries

- **Decision**: Keep transport (`api`), use-case coordination (`application`), framework-free
  domain primitives (`domain`), and adapters (`infrastructure`) separate. The foundation only
  introduces shared error/result contracts and the dependency seam.
- **Rationale**: Forecasting and inventory must remain deterministic and independently testable.
  Establishing the boundary before business code prevents route handlers from becoming the domain.
- **Alternatives considered**: A flat `routers + models` layout or full CQRS/event infrastructure.
  Rejected as either too coupled or too complex for the MVP.

## Decision 5: Contract generation

- **Decision**: FastAPI's OpenAPI document is exported to `openapi/openapi.json` in a deterministic
  command and checked in the API repository. Web pins a copy and records the API commit/tag.
- **Rationale**: Two public repositories need an explicit, reviewable boundary without importing
  backend source. A snapshot makes accidental contract changes visible in pull requests.
- **Alternatives considered**: Hand-written API types in Web, GraphQL, or runtime-only discovery.
  Rejected because they duplicate types or hide breaking changes.

## Decision 6: Model routing for this feature

- **Decision**: Luna writes the architecture/plan, Sol implements, Terra reviews security and
  migrations, GLM-5.3 performs long-context artifact analysis, and SWE-1.7 handles bounded fixes.
- **Rationale**: This is the approved Uribap model policy and separates authorship from review.
- **Alternatives considered**: Kimi K3 as a default. Kept only as an explicit high-cost escalation
  when the cross-repository artifact set is unusually large.
