<!--
Sync Impact Report
Version change: template → 1.0.0
Modified principles: none; replaced the generated placeholders with API governance.
Added sections: backend constraints, workflow and model policy.
Removed sections: none; the template placeholders were resolved.
Deferred items: exact dependency versions are selected during foundation after release-age and security checks.
-->
# Uribap API Constitution

## Core Principles

### I. Domain Correctness Is Non-Negotiable
The backend MUST preserve the distinction between actual inventory, projected demand, and
confirmed consumption. Planning or editing a meal MUST NOT mutate physical inventory.
Completing a meal MUST use an auditable, transactional movement and MUST never create a
negative physical lot balance. Recipe versions, lot allocations, corrections, and reversals
MUST preserve historical truth.

### II. Deterministic Domain Services
Forecasting, shopping, preparation, quantity scaling, unit normalization, and reconciliation
MUST live in framework-independent domain services. They MUST be deterministic, side-effect
free at the calculation boundary, and testable without FastAPI or PostgreSQL. API routes MUST
coordinate use cases rather than contain business calculations.

### III. Test-First Critical Paths
Every change to quantities, units, inventory, planning, projections, shopping, preparation,
completion, or reconciliation MUST include domain tests before implementation. Integration tests
MUST cover PostgreSQL transactions, tenant isolation, idempotency, optimistic concurrency, and
contract behavior. A feature is not complete while its critical acceptance scenarios are
untested.

### IV. Tenant Isolation and Secure Identity
Every tenant-owned query and mutation MUST be scoped to a household membership. The API MUST
validate OIDC issuer, audience, signature, expiry, and required scopes. Passwords and identity
provider secrets MUST NOT be stored in Uribap or logged. Error responses and logs MUST avoid
secrets, tokens, and unnecessary personal data.

### V. Contract-First API Evolution
REST resources and domain operations MUST be represented in the generated OpenAPI contract.
The API repository owns the canonical contract; breaking changes require a new API version.
Web clients MUST consume a generated client from a pinned contract snapshot. Errors, decimal
quantities, pagination, idempotency, and concurrency conflicts MUST be documented and tested.

### VI. Resource-Aware Simplicity
Uribap API MUST remain a modular monolith. New infrastructure such as queues, caches,
workers, or services requires a written rationale tied to a measured need. The default runtime
MUST operate with a small connection pool and one API worker within the shared VPS budget.
Derived projections MUST be rebuildable so future asynchronous processing does not change domain
semantics.

### VII. Reproducible, Auditable Operations
Database changes MUST use reviewed Alembic migrations. Inventory and consumption changes MUST
have append-only movement/audit records. Builds MUST use lockfiles and pinned, sufficiently
mature releases. Docker health checks, structured logs, backup/restore verification, and
security/dependency scans are release gates.

## Backend Constraints

- Python/FastAPI, PostgreSQL, SQLAlchemy 2, Alembic, and Pydantic are the planned stack.
- Quantities MUST use Decimal/NUMERIC; supported MVP dimensions are count, mass, and volume.
- The MVP MUST support units, grams, kilograms, milliliters, and liters without cross-dimension guesses.
- Food, product, or recipe images MUST NOT be stored or uploaded.
- Nutrition, marketplace integrations, grocery delivery, real-time collaboration, and LLM-based
  calculations are out of scope for the MVP.
- Authentication is delegated to a provider-neutral OIDC boundary; ZITADEL is the selected
  deployment provider, while household roles remain application data.
- Email credentials, database credentials, API keys, and secrets MUST be environment-managed
  and absent from public repositories.

## Development Workflow and Model Policy

- Each feature MUST follow Spec Kit: constitution → specify → clarify → plan → checklist →
  tasks → analyze → implement → converge.
- Every feature `plan.md` MUST record its primary model, reviewer model, subagent model, and
  escalation condition using identifiers verified by `devin models list --format json`.
- Recommended defaults as of 2026-09-08: `gpt-5-6-luna-max` for domain/architecture,
  `gpt-5-3-codex-high` for implementation, `claude-opus-5-high` for security/transaction
  review, and `swe-1-7` for bounded test fixes. Adaptive MAY be used for mixed low-risk work.
- Model selection is a tool policy, not a domain dependency. If a model is unavailable, the
  work MUST stop for reassignment rather than silently weakening a critical review.
- A pull request MUST identify migrations, contract changes, tests, security implications, and
  deployment impact. Commits MUST be in English and focused on one coherent change.

## Governance

This constitution is the highest-priority project governance document for `uribap-api`.
Spec, plan, task, code, and review artifacts MUST comply with its MUST statements. Amendments
require a dated Sync Impact Report, a semantic version bump, and review of affected specs/tasks.
A major version changes or removes a principle; a minor version adds a principle or materially
expands governance; a patch version clarifies wording without changing obligations. Any
constitution conflict found by analysis is blocking until resolved explicitly.

**Version**: 1.0.0 | **Ratified**: 2026-09-08 | **Last Amended**: 2026-09-08
