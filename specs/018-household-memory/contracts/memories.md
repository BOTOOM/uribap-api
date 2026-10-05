# Household Memory REST Contract

All endpoints require authentication and an active membership selected by `X-Household-ID`.
Every memory/diner lookup and list is scoped to the selected household. Foreign and absent ids both
return `404`. Any active household role may read or mutate memories.

`kind` is one of `like`, `dislike`, `restriction`, `goal`, or `note`. `content` is trimmed and must
contain 1–1000 characters.

## `GET /api/v1/memories`

Query:

- `diner_id: UUID | null` (optional)
- `scope: all | household | diner` (default `all`)
- `include_archived: boolean = false`
- `limit: integer = 200`, range 1–200.

`scope=household` returns only rows with null `diner_id`; `scope=diner` returns diner-scoped rows
and optionally narrows to `diner_id`; `scope=all` includes both scopes and may be narrowed by
`diner_id`. By default the list excludes archived memories and memories of archived diners.
`include_archived=true` includes both. Results are ordered household-level first, then diner id,
kind, and creation time. Returns `200 MemoryPage`.

## `POST /api/v1/memories`

Optional header: `Idempotency-Key` (maximum 128 characters).

Request `MemoryCreate`:

```json
{
  "kind": "restriction",
  "content": "Avoid peanuts",
  "diner_id": "optional active diner UUID"
}
```

Omitting `diner_id` creates a household-level memory. A supplied id must be an active diner in this
household; an absent, archived, or foreign diner returns `404`.

Success: `201 MemoryResponse`. Identical key and payload replay returns the same created memory;
reusing the key for another payload returns `409`.

## `PATCH /api/v1/memories/{memory_id}`

Request `MemoryUpdate`:

```json
{
  "kind": "like",
  "content": "Enjoys lentils",
  "diner_id": null,
  "expected_version": 1
}
```

At least one of `kind`, `content`, or `diner_id` must be supplied. Omitted properties remain
unchanged; explicit null `diner_id` moves the memory to household scope. `expected_version` is
required (`>= 1`). A stale version returns `409`. A non-active, absent, or foreign diner target
returns `404`. Archived memory ids are not patchable.

Success: `200 MemoryResponse`.

## `DELETE /api/v1/memories/{memory_id}`

Soft-archives a memory and returns `204 No Content`. Repeating archive on an already archived memory
also returns `204`.

## `GET /api/v1/memory/profile`

Returns `200 HouseholdMemoryProfile` containing:

- `household: MemoryResponse[]` — active memories with null `diner_id`.
- `diners: { diner: DinerResponse, memories: MemoryResponse[] }[]` — active diners and only their
  active memories.

Archived diners and memories never appear in this profile.

## Response fields

`MemoryResponse`: `id`, `diner_id`, `kind`, `content`, `archived_at`, `version`,
`created_by_user_id`, `created_at`, `updated_at`.

`MemoryPage`: `items: MemoryResponse[]`.

## Domain events and privacy

Mutations record `memory.created`, `memory.updated`, or `memory.archived`. Payloads may contain
resource ids and `kind` only. Memory content and diner display names are not event fields and are
not logged.
