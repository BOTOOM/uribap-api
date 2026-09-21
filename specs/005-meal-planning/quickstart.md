# Quickstart: Meal Planning

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/api
docker compose up -d db
uv run alembic upgrade head
uv run pytest tests/integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

Create a draft plan for a Monday, add an entry with a published recipe version, propose, approve with a different member, and verify version conflicts, append-only events, and idempotent replays. Planning must never change `inventory_lot`/`inventory_movement`.

## Evidence (2026-09-21)

- `uv run ruff check .` / `ruff format --check .`: PASS.
- `uv run pyright`: 0 errors.
- `uv run pytest tests/unit tests/api`: PASS, including 22 planning policy cases and the OpenAPI route contract test.
- `uv run pytest tests/integration/test_planning_schema.py` (PostgreSQL): 5 passed — table structure, state CHECK constraints, append-only trigger, unique active week, idempotency uniqueness.
- `uv run pytest tests/integration/test_planning_service.py` (PostgreSQL): 6 passed — full draft→propose→approve flow, optimistic `expected_version` 409, stored-payload idempotent replay and hash-conflict 409, `notes: null` clearing, `recipe_version_id` swap, approver separation, reopen-note 422, delete version bump.
- `export_openapi --check`: PASS; `/plans*` routes and Problem Details responses exported.
- `uv run pip-audit`: no known vulnerabilities.
- Docker image build: PASS (`uribap-api:005`).
- Known local limitation: `test_inventory_schema` fails on the pre-hardening local f4 database (documented in 004 converge); clean-database CI is canonical.

