# Checklist — 015 Review Follow-up

- [x] The integration test holds the migration advisory lock on a separate PostgreSQL connection.
- [x] `migrate.main()` remains blocked while another session holds the lock.
- [x] Releasing the lock lets `migrate.main()` finish with exit code 0 within the test timeout.
- [x] The test releases its lock even if an assertion fails and leaves no background thread running.
- [x] Existing migration idempotency, Ruff, Pyright, full-suite, and Alembic checks pass.
