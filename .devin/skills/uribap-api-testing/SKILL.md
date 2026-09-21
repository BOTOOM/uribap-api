---
name: uribap-api-testing
description: Run the Uribap API verification workflow for a feature, including domain tests, PostgreSQL integration, migrations, OpenAPI, security, and resource checks.
argument-hint: "[feature or scope]"
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - glob
  - exec
---

# Uribap API Testing Workflow

Use this skill before declaring any API feature complete. The active feature's `spec.md`,
`plan.md`, `tasks.md`, `.specify/memory/constitution.md`, and `AGENTS.md` are authoritative.

## Non-negotiable rules

- Do not modify application code, specs, tasks, migrations, or configuration while running this
  skill. Report proposed fixes separately.
- Do not run destructive commands such as `docker compose down -v`, `rm`, database drops, or bulk
  deletion. A test database must be isolated and disposable only with explicit user approval.
- Never use production credentials, Brevo credentials, real user data, or production OIDC issuers.
- Domain calculations must be tested without FastAPI/PostgreSQL before integration tests.
- A feature cannot be reported green if its required test command was skipped or failed.
- UV is mandatory for every Python operation: use `uv sync --locked`, `uv add`, and `uv run`.
  Never use `pip install`, create/activate a manual virtualenv, or edit `uv.lock` by hand.

## Required verification order

1. Read the active feature artifacts and map each FR/SC/user-story acceptance scenario to tests.
2. Validate static quality:

   ```bash
   uv run ruff check .
   uv run pyright
   ```

3. Run pure and API tests:

   ```bash
   uv run pytest tests/unit
   uv run pytest tests/api
   ```

4. Start only the required local database stack and apply migrations:

   ```bash
   docker compose up -d db
   uv run alembic upgrade head
   uv run pytest tests/integration
   ```

5. Run contract and security checks:

   ```bash
   PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
   uv run pip-audit
   ```

6. Build and smoke-test Docker when the feature plan requires it:

   ```bash
   docker compose up -d --build
   RUN_COMPOSE_SMOKE=1 uv run pytest tests/integration/test_compose_health.py
   docker compose ps
   ```

7. Measure the API process and database memory with `docker stats --no-stream`; compare against
   the feature's resource budget and record observed values in its quickstart/runbook.

## Domain feature gates

For inventory, forecast, shopping, preparation, completion, and reconciliation features, require:

- deterministic pure tests;
- decimal/unit edge cases;
- no planned-meal mutation of actual inventory;
- lot allocation and no-negative invariants;
- idempotency and optimistic concurrency;
- PostgreSQL transaction/locking tests;
- OpenAPI request/response/error coverage;
- tenant isolation tests.

## Local identity testing

When the feature touches authentication or household membership, use the local identity skill and
Docker Compose with a disposable ZITADEL instance, its dedicated PostgreSQL database, and Mailpit.
Do not configure Brevo or any external SMTP service locally. Email verification, password reset,
and invitation messages must be inspected in Mailpit; the test must not send real email.

## Report format

Return a table with command, result, skipped tests, warnings, security findings, resource sample,
and unresolved task IDs. Distinguish `PASS`, `FAIL`, and `NOT RUN`; never turn an unavailable
external dependency into a false pass.
