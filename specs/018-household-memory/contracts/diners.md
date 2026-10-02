# Diner REST Contract

All endpoints require authentication and an active membership selected by `X-Household-ID`.
Every id lookup is scoped to that household; foreign and absent diner ids both return `404`.
Any active household role may read or mutate diners.

## `GET /api/v1/diners`

Query:

- `include_archived: boolean = false`.

Returns `200 DinerPage` with `items: DinerResponse[]`. Results are scoped to the selected
household and ordered deterministically by display name, then id. Archived diners are omitted
unless `include_archived=true`.

## `POST /api/v1/diners`

Optional header: `Idempotency-Key` (maximum 128 characters).

Request `DinerCreate`:

```json
{
  "display_name": "Alex",
  "member_user_id": "optional UUID"
}
```

`display_name` is trimmed and must contain 1–80 characters. `member_user_id` is optional and may be
null. A non-null id must be an active member of the selected household (`422` otherwise); a name or
member link conflict returns `409`.

Success: `201 DinerResponse`. Identical key and payload replay returns the same created diner;
reusing the key for another payload returns `409`.

## `PATCH /api/v1/diners/{diner_id}`

Request `DinerUpdate`:

```json
{
  "display_name": "New name",
  "member_user_id": null,
  "expected_version": 1
}
```

At least one of `display_name` or `member_user_id` must be supplied. Omitted fields remain
unchanged; explicit `member_user_id: null` unlinks the account. `expected_version` is required
(`>= 1`). A stale version returns `409`. A duplicate name/member link returns `409`; a non-active or
foreign member link returns `422`.

Success: `200 DinerResponse`. Patches to archived diners return the standard not-found response.

## `DELETE /api/v1/diners/{diner_id}`

Soft-archives an active diner, preserving its memories. Returns `204 No Content`; archiving an
already archived diner is also `204` and emits no additional event. Archived diners and their
memories are omitted from the default active profile. The unique member link is retained unless
explicitly cleared before archive.

## `DinerResponse`

Contains exactly the resource fields:

- `id`
- `display_name`
- `member_user_id`
- `archived_at`
- `version`
- `created_at`
- `updated_at`

## Events

Mutations record `diner.created`, `diner.updated`, or `diner.archived`. Payloads may contain diner
and member ids but never the display name.
