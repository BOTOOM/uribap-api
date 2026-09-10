# Uribap API Engineering Guide

## Scope

This repository owns the FastAPI backend, PostgreSQL schema/migrations, deterministic domain
services, canonical OpenAPI contract, and Coolify deployment configuration for Uribap.

## Required workflow

- Read `.specify/memory/constitution.md` and the active feature artifacts before changing code.
- Follow Spec Kit in order: specify, clarify, plan, checklist, tasks, analyze, implement, converge.
- Every roadmap item MUST have its own complete feature spec, plan, data model/contracts when relevant,
  tasks, tests, analyze result, implementation, and convergence before it is considered done.
- No product code may start before the active spec/plan/tasks/analyze gate is complete, and no task
  may be closed without its documented tests and quickstart validation.
- Keep domain calculations framework-independent and use `Decimal` for quantities.
- Add or update domain tests before implementation for inventory, forecast, shopping, preparation,
  completion, reconciliation, and concurrency changes.
- Keep API errors, quantities, idempotency, and optimistic concurrency in the OpenAPI contract.
- Never log or commit credentials, tokens, personal data beyond what the feature requires, or food
  images.

## Verification

Expected checks will be documented in the active feature plan. Foundation targets include Ruff,
type checking, unit/integration/API tests, Alembic validation, OpenAPI generation, and Docker
health checks.

## Reusable testing skills

- Use `/uribap-api-testing` before closing any API feature; it runs the project-specific quality,
  migration, contract, security, and resource gates without editing code.
- Use `/uribap-local-identity-testing` for OIDC/household features. Local complete email flows use
  Docker Compose with ZITADEL, dedicated PostgreSQL, and Mailpit; Brevo is never used locally.

## Model guidance

Use the model matrix in the active `specs/*/plan.md`. As of 2026-09-10, prefer
`gpt-5-6-luna-max` for domain architecture, `gpt-5-6-sol-high` for implementation,
`gpt-5-6-terra-high` for security/transaction review, `glm-5-3-max` for long-context
analysis, `kimi-k3-max` only for explicit cross-repo escalation, and `swe-2-high` for bounded fixes.
