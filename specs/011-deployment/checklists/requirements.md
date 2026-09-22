# Requirements Checklist: Deployment Hardening

- [x] Baseline security headers on every API response (FR-001)
- [x] `no-store` on `/api/v1` JSON responses (FR-001)
- [x] Docs paths reachable and unrestricted by CSP (FR-001)
- [x] `.env.example` documents `EMAIL_DELIVERY_ENABLED=false` and all settings (FR-002)
- [x] Coolify runbook: env table, health, migration step, dispatcher, rollback (FR-003)
- [x] No secrets/tokens in headers, health output, or docs (FR-004)
- [x] OpenAPI and Alembic unchanged (FR-005)
