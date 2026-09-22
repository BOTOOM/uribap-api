# Contract Notes: Activity Feed

## GET /api/v1/households/{household_id}/activity

Query: `page` (default 1), `page_size` (default 20, max 100).

200 `ActivityFeedResponse`:

- `entries`: `ActivityEntry[]` — `id`, `kind`, `occurred_at`, `actor_user_id`
  (nullable), `aggregate_type`, `aggregate_id` (nullable), `payload`.
- `page`, `page_size`, `has_more`.
- `outbox`: `OutboxSummary` — counts of the household's invitation email intents
  by status (`pending`, `sent`, `failed`, `suppressed`).

Errors: 401 unauthenticated, 403 not an ACTIVE member, 404 household not found.

## Internal dispatcher (no HTTP surface)

`uv run python -m uribap_api.tools.process_outbox --limit N` exits 0 and prints
claimed/suppressed/sent/failed counts.
