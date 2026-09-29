# Checklist — 016 ZITADEL household invitations

- [x] ZITADEL settings use issuer fallback, normalized URLs, paired credentials, and production HTTPS.
- [x] Directory requests use exact case-insensitive lookup, required profile names, `returnCode: {}`, and the correct Login V2 invite template.
- [x] Service token, recipient email, and response bodies are absent from exception messages and error logs.
- [x] New, existing, failed, and SMTP delivery paths return distinct delivery values and update outbox status.
- [x] Directory mode never invokes SMTP and failure leaves the invitation persisted.
- [x] Pending invitation listing is limited to verified, normalized email, pending state, and unexpired entries.
- [x] By-ID acceptance conceals another email's invitation and uses the same locked-row acceptance behavior as token acceptance.
- [x] Token acceptance preserves its existing membership, audit, and event effects.
- [x] No database migration is introduced and the exported OpenAPI contract is current.
- [x] Coolify documentation explains ZITADEL setup and the SMTP fallback.
- [x] Required Ruff, Pyright, tests, Alembic, OpenAPI, and diff checks pass.
