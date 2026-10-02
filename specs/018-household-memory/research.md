# Research: Household Diners and Memory

## Decision: Model diners separately from household memberships

Store each eater as a `household_diner`, with an optional link to an active household member
account. A diner can therefore represent an invited partner or other person without an Uribap
login.

### Rationale

- A household membership represents authorization and identity, not necessarily everyone who eats
  in the home.
- Diner records support both account-linked and account-less people with the same memory model.
- The specified unique member link prevents one account from representing multiple diners in a
  single household.

### Alternatives considered

- **Attach preferences to `household_member`**: Rejected because account-less diners could not have
  individual memory.
- **Use display-name strings directly on memories**: Rejected because rename, archive, and
  uniqueness semantics would be duplicated and references could become ambiguous.

## Decision: Normalize diners and memories into separate versioned tables

Create `household_diner` and `household_memory` with household ownership, soft archive timestamps,
optimistic versions, and indexes/constraints specified by the feature contract.

### Rationale

- Separate rows support reliable CRUD, idempotency, household isolation, and audit events.
- A nullable `diner_id` represents household-level memory without a sentinel diner.
- Foreign keys enforce cascade when a household/diner is deleted while the API uses soft archive
  for normal history-preserving operations.

### Alternatives considered

- **One JSON profile per household**: Rejected because individual memories need independent updates,
  versions, archive behavior, ids, and event history.
- **Hard-delete diners/memories**: Rejected because archive preserves history and the design
  requires archived diner memories to remain stored.

## Decision: Enforce active-name uniqueness in PostgreSQL

Trim display names at the schema boundary and use the specified partial unique index over
`(household_id, lower(display_name))` for rows with `archived_at IS NULL`. Use the separate
household/member unique constraint for optional member links.

### Rationale

- Database uniqueness covers concurrent creates and renames, including differing letter casing.
- The partial predicate permits reuse of an archived display name.
- The member link constraint remains effective for archived rows, as required by the stated
  non-partial unique constraint.

## Decision: Use presence-aware optimistic patches

Require `expected_version` in REST update bodies and distinguish an omitted optional property from
an explicitly supplied `null`. Lock the tenant-owned row before comparing versions and applying
changes; increment its version on successful updates.

### Rationale

- Explicit null unlinks a diner account or moves a memory to household scope.
- The existing API uses `expected_version >= 1` and `409` for stale writes.
- Pydantic's `model_fields_set` provides the presence distinction without custom request formats.

## Decision: Soft archive and active-only profile

Archive diners and memories by setting `archived_at`. The active profile contains only unarchived
household memories and unarchived diners with their unarchived memories. A diner archive does not
rewrite its child memories; opt-in archived listings can show retained rows.

### Rationale

- Historical memory remains available for explicitly inclusive reads.
- Normal profile reads stay focused on current household preferences.
- Repeated diner archive is an idempotent `204` with no duplicate event.

## Decision: Reuse household-scoped operation receipts

Use `MealPlanOperation` with distinct operation names for diner and memory creates, reusing its
household/operation/idempotency-key uniqueness, request fingerprint, JSON result payload, and
concurrent replay handling. No new receipt table or migration is needed.

### Rationale

- The existing table has no mandatory meal-plan foreign key and is the repository's established
  idempotency mechanism for plan entry creation.
- Operation-specific names keep keys independent between create operations and other features.

## Decision: Record privacy-minimized domain events

Extend `DomainEventKind` with the six specified diner/memory events. Store resource ids and memory
kind only in event payloads; do not include memory text or diner display names.

### Rationale

- Events preserve an auditable mutation trail while minimizing personal data.
- Existing persistence enforces a non-empty event kind but has no closed enum constraint, so these
  values do not require changes to the domain-event migration.

## Decision: Define memory listing filters compositionally

`scope=household` filters to `diner_id IS NULL`; `scope=diner` filters to non-null diner ids and may
be narrowed by the supplied `diner_id`; `scope=all` has no scope restriction and may also be
narrowed by `diner_id`. `include_archived=true` includes archived memories and memories of archived
diners. All results remain household-scoped and ordered household-level first, then diner id,
kind, and creation time.

### Rationale

- This makes each query parameter independently composable and supports both household and
  all-diner review without another endpoint.
- It aligns with the active-only profile while retaining an explicit path to archived history.

## Decision: Resolve MCP diner names inside the authorized household

`uribap_remember` accepts either a diner id or a diner name, but not both. Names are matched
case-insensitively among active diners in the current household. Unknown names return a clear
create-first error; no name or id means household-level memory.

### Rationale

- It is convenient for agents that have just read the profile, without permitting cross-household
  name lookup.
- Rejecting simultaneous id and name avoids silent precedence choices.

## Decision: Generate OpenAPI from the canonical application

Regenerate `openapi/openapi.json` with the repository exporter after routers and Pydantic models are
complete, then run its `--check` mode and contract tests.

### Rationale

The new resources and profile are public API changes. Manual snapshot edits would bypass the
canonical route/schema implementation.
