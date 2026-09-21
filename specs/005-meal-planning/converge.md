# Convergence: Meal Planning and Collaboration

**Status**: Implementation complete pending clean-database CI confirmation.

## Implemented

- Pure state machine and version policy (`domain/planning/policies.py`): `draft → proposed → approved`, `proposed|approved → draft` reopen (mandatory note from `approved`), terminal `archived`; approver MUST differ from proposer when ≥2 active members and a proposer must exist; typed `PlanEntryDraft` validation.
- Persistence: `meal_plan` (partial unique index for one active plan per household-week), `meal_plan_entry` (slot uniqueness, composite tenant FK), `meal_plan_state_event` (append-only trigger, `from_state`/`to_state` CHECK constraints, composite tenant FK), `meal_plan_operation` (operation-scoped idempotency receipts with request hash and stored result payload).
- Service: `SELECT FOR UPDATE` plan locking, verify-then-bump versioning (no dirty state on failed mutations), `IntegrityError`→409 translation covering flush-time conflicts, collision-aware idempotent replay returning the stored original response, `notes: null` clearing via `model_fields_set`, `recipe_version_id` swap with published validation, reopen-without-note 422, `GET /recipes/published-versions` picker endpoint.
- Problem Details 401/403/404/409/422 declared on every route; OpenAPI snapshot regenerated.
- Spec clarifications: `expected_version` scoped to existing plans (creation serialized by the unique index), `approved` reopen semantics, PATCH field set, per-layer delivery impact summary.

## Evidence

- Local gates: Ruff/format/Pyright PASS; 52 unit/API tests; 11 PostgreSQL planning tests; OpenAPI export check; pip-audit; Docker build. See `quickstart.md`.
- Review round 1 findings across the four stacked PRs were resolved (spec contradictions, approver bypass, event CHECK constraints, flush-time IntegrityError mapping, stored-payload replay, concurrent key collision, notes clearing, entry PATCH, reopen 422, behavioral tests).

## Remaining gates

- Confirm GitHub quality on a clean PostgreSQL service for the full suite (the legacy local database predates the hardened 004 schema, so `test_inventory_schema` fails locally as documented in phase 004).
- Web UI consumes this contract; merge order: Web stack first while `contract.yml` still references the API service branch, then API stack, then the `ref: main` cleanup PR.
- No email delivery or deployment is required for this feature.
