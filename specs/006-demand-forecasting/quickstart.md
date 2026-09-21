# Quickstart: Demand Forecasting

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

Seed an approved plan with entries, add inventory lots (one expired before the window), and call `GET /forecast/demand?from_date=…&to_date=…` twice; payloads MUST be identical, expired stock MUST NOT count, and no table row changes.

## Evidence (2026-09-21)

- `uv run ruff check .` / `ruff format --check .`: PASS.
- `uv run pyright`: 0 errors.
- `uv run pytest tests/unit`: PASS — 16 forecast policy cases (window validation, Decimal scaling, per-unit aggregation, optional split, zero-line suppression, on-hand/shortfall).
- `uv run pytest tests/api`: PASS — `/api/v1/forecast/demand` OpenAPI contract test (GET only, 401/403/422 Problem Details, window params).
- `uv run pytest tests/integration/test_forecast_service.py` (PostgreSQL): 4 passed — scaled demand with shortfall and expired-lot exclusion, draft-plan exclusion, deterministic replay + read-only (no operation receipts), window validation + tenant isolation.
- `export_openapi --check`: PASS; `/forecast/demand` exported.
- `uv run pip-audit`: no known vulnerabilities.
- Docker image build: PASS (`uribap-api:006`).
- No new migrations: the projection reads existing tables only.
