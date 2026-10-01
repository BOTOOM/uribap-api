# Implementation Plan: Household Diners and Memory

**Branch**: `devin/1790821649-household-memory` | **Date**: 2026-10-01 |
**Spec**: [spec.md](spec.md)

## Summary

Add tenant-scoped diner profiles, durable household/diner memories, a combined active profile, REST
CRUD endpoints, and MCP tools for agents. Persist the resources with one reversible migration after
the verified API 017 head. Event payloads identify changed resources and memory kind without
capturing memory text or display names.

## Models

- Primary: `gpt-5-6-luna-max` for architecture and domain boundaries; implementation: `gpt-5-6-sol-high`;
  reviewer: `gpt-5-6-terra-high` for tenant isolation/privacy/transactions; subagent: `swe-2-high`
  for bounded test fixes.
- The model identifiers follow the API `AGENTS.md` matrix. `devin models list --format json` is
  unavailable in this environment, matching the documented exception in features 014 and 017.
  Identifiers are not represented as tool-verified.
- Escalate to the lead only if the authoritative design contradicts the existing schema or requires
  a product decision; otherwise follow established API patterns and record small implementation
  choices in convergence.

## Technical Context

**Language/Version**: Python 3.13+

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic, PostgreSQL

**Storage**: Add `household_diner` and `household_memory` tables in one Alembic migration after
`d3c72b91a84f`.

**Testing**: Domain/unit validation plus PostgreSQL service, API, MCP, idempotency, tenant, event,
and migration tests; Ruff, Pyright, generated OpenAPI validation

**Target Platform**: Linux container on Coolify

**Project Type**: FastAPI web service and MCP server

**Constraints**: All queries and writes are household-scoped; active membership is sufficient for
all roles. Memory content is never placed in log messages or domain-event payloads. UV remains the
only Python environment/package manager.

**Scale/Scope**: Two tables, one additive migration, three resource collections (diners, memories,
profile), and seven memory/diner MCP tools. No Web UI, automated memory extraction, or meal-planning
changes.

## Design

### A. Diner profiles

- Add `MemoryKind` in `src/uribap_api/domain/household/memory.py`.
- Add `HouseholdDiner` to persistence with household cascade, nullable user `SET NULL` link,
  version/timestamps, household/member uniqueness, and a partial case-insensitive unique index for
  active names.
- Require a trimmed 1–80 character name. Validate member links against active membership in the
  same household; use `422` for invalid membership and `409` for uniqueness conflicts.
- Updates use body `expected_version >= 1`, row locking, and presence-aware patch semantics.
  Archives are soft and idempotent; they do not delete or separately archive memory rows.

### B. Household and diner memories

- Add `HouseholdMemory` with nullable diner scope, kind check constraint, created-by user reference,
  soft archive, version, and timestamps.
- Validate and trim content to 1–1000 characters in Pydantic schemas. Every supplied diner id must
  resolve to an active diner of the caller's household.
- Scope every lookup, mutation, and list by `membership.household_id`. Foreign ids return `404`.
- Updates use `expected_version` and explicit field-presence semantics. Null `diner_id` moves a
  memory to household scope.
- Record only ids and `kind` in the six required domain event types. Never log or emit display names
  or memory content. Extend the existing typed `DomainEventKind`; its persisted model checks only
  that event kind is non-empty.
- Use `MealPlanOperation` receipts/fingerprints for the two POST endpoints, with operation-specific
  names and household uniqueness.

### C. REST profile and CRUD

- Add Pydantic request/response schemas and `api/memory.py`.
- Mount the router through `api/router.py`; all paths use the shared
  `get_active_household_membership` dependency.
- Provide the exact collection/detail paths and status codes in the contract. Mutation conflict,
  validation, authentication, and not-found errors use the existing `DomainError` and
  `ProblemDetails` patterns.
- `GET /memory/profile` reads only active memories and active diners. `GET /memories` supports
  scope, diner, archive, and bounded limit filters with deterministic household-first ordering.

### D. MCP memory tools and context

- Add and register `mcp/tools_memory.py`.
- Use READ_ONLY for profile reads and WRITE for mutations. Resolve `diner_name` with
  case-insensitive matching across active diners in the current household; unknown names return a
  ToolError instructing the agent to create the diner first.
- MCP update tools load the current version when `expected_version` is omitted, following
  `uribap_update_household`.
- Extend `uribap_get_context` and its description with the active profile.

### E. Migration and OpenAPI

- Create one revision with `down_revision = "d3c72b91a84f"`.
- Generate `openapi/openapi.json` only with
  `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi`; verify with `--check`.

## Constitution Check

- **Domain correctness**: Pass. Diner identities are distinct from login accounts, and household
  memory is explicitly scoped without changing food/inventory calculations.
- **Deterministic services**: Pass. CRUD and profile assembly use tenant-scoped SQLAlchemy queries;
  no model inference or external service is introduced.
- **Test-first**: Pass. Add schema, service, route, MCP, event, idempotency, tenant, and migration
  tests before product implementation.
- **Tenant isolation/privacy**: Pass. Every query includes membership household id; errors hide
  foreign ids; events and logs exclude memory text and diner names.
- **Contract-first**: Pass. All request/response schemas and errors are generated into the
  canonical OpenAPI artifact and tested.
- **Resource-aware**: Pass. Reuse the existing DB, domain-event, and idempotency infrastructure;
  no new runtime service or dependency.
- **Operations**: Pass. One Alembic migration is reversible and validated with upgrade/downgrade/
  upgrade; no schema drift is hand-applied.
- **Model policy exception**: Lead-approved. The CLI is unavailable; use the identifiers in
  `AGENTS.md` and do not claim live tool verification.

## Required Verification

Run in this order:

1. Focused new/changed unit, integration, API, MCP, and migration tests with `uv run pytest ... -q`.
2. `uv run alembic upgrade head`, `uv run alembic downgrade -1`,
   `uv run alembic upgrade head`, then `uv run alembic heads` (one head).
3. `uv run ruff check src tests` and `uv run ruff format --check` on every touched Python file.
4. `uv run pyright`.
5. Regenerate OpenAPI with the repository tool, run `--check`, and pass contract tests.
6. Run the final full `uv run pytest -q`.
7. Run `git diff --check` and record evidence/deviations in `converge.md`.

## Complexity Tracking

No constitutional violations or new infrastructure are proposed.
