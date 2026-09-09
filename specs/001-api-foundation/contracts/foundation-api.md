# Foundation API Contract

The API repository owns the canonical contract. Web consumes a pinned copy of this document's
OpenAPI representation after the foundation service is scaffolded.

## Required foundation routes

- `GET /api/v1/health/live`: process-only health; HTTP 200 when routing is available.
- `GET /api/v1/health/ready`: dependency-aware readiness; HTTP 200 when required persistence is
  available and HTTP 503 otherwise.
- Generated OpenAPI document: stable schema, error components, and shared response metadata.

## Error envelope

All validation, routing, unsupported-content, and operational errors use an RFC 9457-compatible
JSON object with `type`, `title`, `status`, `detail`, `instance`, `code`, and `requestId`.
Stack traces, secrets, credentials, and authorization headers are never returned.

## Representation rules

- Public JSON names use camelCase.
- Timestamps are ISO 8601 UTC.
- Future decimal quantities use string amounts plus explicit units.
- Additive `/api/v1` changes are compatible; breaking changes require a new API version.
- The contract export must be deterministic and checked in at `openapi/openapi.json`.
