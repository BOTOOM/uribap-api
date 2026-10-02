# Data Model: Household Diners and Memory

One additive Alembic migration after `d3c72b91a84f` adds two tables.

## HouseholdDiner

Table: `household_diner`

- `id`: UUID primary key.
- `household_id`: non-null FK to `household.id`, `ON DELETE CASCADE`, indexed.
- `display_name`: non-null `String(80)`, trimmed to 1–80 characters by the request schema.
- `member_user_id`: nullable FK to `app_user.id`, `ON DELETE SET NULL`.
- `archived_at`: nullable timezone-aware timestamp.
- `version`: non-null integer, default `1`.
- `created_at`, `updated_at`: timezone-aware timestamps with server defaults consistent with other
  persistence models.

Constraints and indexes:

- Unique `(household_id, member_user_id)` named `uq_household_diner_member`; multiple null links
  are allowed.
- Partial unique `(household_id, lower(display_name))` named
  `uq_household_diner_active_name`, where `archived_at IS NULL`.
- Index on `household_id`.

## HouseholdMemory

Table: `household_memory`

- `id`: UUID primary key.
- `household_id`: non-null FK to `household.id`, `ON DELETE CASCADE`, indexed.
- `diner_id`: nullable FK to `household_diner.id`, `ON DELETE CASCADE`; null means household-level
  memory.
- `kind`: non-null `String(16)` constrained by `ck_household_memory_kind` to `like`, `dislike`,
  `restriction`, `goal`, or `note`.
- `content`: non-null `Text`; API schemas trim it and enforce 1–1000 characters.
- `created_by_user_id`: nullable FK to `app_user.id`, `ON DELETE SET NULL`.
- `archived_at`: nullable timezone-aware timestamp.
- `version`: non-null integer, default `1`.
- `created_at`, `updated_at`: timezone-aware timestamps with server defaults.

Indexes:

- Index on `household_id`.
- Composite index `(household_id, diner_id, archived_at)`.

## Relationships and invariants

- Diner and memory ids are always resolved together with the active membership household id.
- A memory's diner, when present, must be an active diner in the same household for create/update.
- Diner archive preserves child memory rows; profile reads omit the archived diner and its memories.
- A memory with null `diner_id` is household-level and appears in the profile's `household` array.
- Every update checks and increments the row version under a lock. A stale `expected_version`
  returns `409`.
- Domain events persist a resource aggregate id and a payload containing ids and kind only.

## Idempotency

POST create receipts use the existing `meal_plan_operation` table via
`MealPlanOperation`. The operation is `household_diner_create` or `household_memory_create`; the
receipt is scoped by household, operation and idempotency key and stores the request fingerprint
and response payload.

## Migration

- New revision has `down_revision = "d3c72b91a84f"`.
- Upgrade creates the two tables, foreign keys, uniqueness/check constraints and indexes.
- Downgrade drops `household_memory` then `household_diner`.
