# Uribap API Engineering Guide

## Scope

This repository owns the FastAPI backend, PostgreSQL schema/migrations, deterministic domain
services, canonical OpenAPI contract, and Coolify deployment configuration for Uribap.

## Required workflow

- Read `.specify/memory/constitution.md` and the active feature artifacts before changing code.
- Follow Spec Kit in order: specify, clarify, plan, checklist, tasks, analyze, implement, converge.
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

## Model guidance

Use the model matrix in the active `specs/*/plan.md`. As of 2026-09-08, prefer
`gpt-5-6-luna-max` for domain architecture, `gpt-5-3-codex-high` for implementation,
`claude-opus-5-high` for security/transaction review, and `swe-1-7` for bounded fixes.
