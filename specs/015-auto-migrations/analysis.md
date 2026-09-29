# Analysis — 015 Review Follow-up

## Coverage

- The review's migration-concurrency finding maps to an integration test that holds `MIGRATION_ADVISORY_LOCK_ID` on a real connection while `migrate.main()` runs on another connection in a thread.
- The test asserts the migration command is still waiting after approximately one second, releases the session-level lock, and requires a successful exit within a finite timeout.

## Consistency

- The migration runner already acquires a PostgreSQL session-level advisory lock on a dedicated connection and releases it in `finally`; no application behavior change or migration is needed for this finding.
- `integration_engine` uses the configured database URL, as does `migrate.main()` through `get_settings()`, allowing the test to coordinate both connections against the same PostgreSQL database.
- The existing idempotency integration test remains complementary: it verifies repeat upgrades, while the new test verifies cross-session serialization.

## Risks and mitigations

- A leaked test lock could block later migration tests; release it in a `finally` path and join the worker with a bounded timeout.
- The test must not rely on sleeps as the only synchronization. Use a completion event to prove the migration thread is still blocked, then release and join it.

## Open questions

None. The existing lock constant and real PostgreSQL integration fixture cover the settled design.
