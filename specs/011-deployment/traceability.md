# Traceability: Deployment Hardening and Operations Runbooks

| Requirement | Artifact | Verification |
| --- | --- | --- |
| FR-001 | `infrastructure/security_headers.py`, `main.py` | API header tests |
| FR-002 | `.env.example` | env-parity test/manual diff vs `Settings` |
| FR-003 | `docs/operations/coolify.md` | runbook review, commands re-run locally |
| FR-004 | middleware only sets static headers | grep headers for dynamic values |
| FR-005 | no schema/contract diffs | `export_openapi --check`, `alembic check` |
