# Data Model: API Foundation

This feature deliberately establishes infrastructure records and contracts without introducing
Uribap business-domain tables. The later identity, recipe, inventory, and projection specs own
those entities.

## Configuration Contract

| Field | Type | Required | Rule |
|---|---|---:|---|
| `environment` | enum | yes | `development`, `test`, or `production`; no insecure implicit default |
| `database_url` | secret URL | yes for readiness | Never serialized in health or error responses |
| `log_level` | enum | no | Safe default, validated against supported levels |
| `cors_origins` | list of origins | yes outside local development | Explicit origins only; no wildcard in production |
| `api_version` | string | yes | Matches the public `/api/v1` boundary |
| `request_id` | string | generated/accepted safely | Correlation value is bounded and sanitized |

## Runtime Health State

- `live`: process and routing are available; it must not require PostgreSQL.
- `ready`: process and required database connection/migration state are available.
- `not_ready`: dependency unavailable, migration mismatch, or invalid startup state; response
  contains safe diagnostic code, not credentials or connection strings.

## Migration Baseline

- `alembic_version`: tool-owned revision pointer.
- No application business table is created by this feature.
- Future domain migrations must be forward-only in normal deployment, reviewed, and accompanied
  by rollback/restore notes when data changes are destructive.

## Contract Value Objects

- `ProblemDetails`: `type`, `title`, `status`, `detail`, `instance`, optional `code`, and
  `request_id`; `detail` is safe for end users and does not expose stack traces.
- `Quantity`: string decimal amount plus explicit unit; binary floats are not valid contract values.
- `PageInfo`: reserved cursor/limit shape for future list endpoints.
- `MutationMeta`: reserved projection revision/idempotency/concurrency metadata for future domain
  commands; foundation only documents the shape and does not implement business mutations.
