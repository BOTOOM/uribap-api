# Feature Specification: Household Diners and Memory

**Feature Branch**: `devin/1790821649-household-memory`
**Status**: Ready for implementation

## User Scenarios & Testing

### User Story 1: Keep household diners distinct from user accounts (Priority: P1)

A household member creates a diner profile for each person who eats in the household. A diner can
be linked to an active household member account, or represent someone who has no Uribap account.
Members can rename, link, unlink, list, and archive diner profiles.

**Independent Test**: Create linked and unlinked diners, list them, update one with the current
version, archive it, and confirm a case-insensitive duplicate active name conflicts while the
archived name can be reused.

**Acceptance Scenarios**:

1. **Given** an active household member, **When** they create a diner with a trimmed display name,
   **Then** the API returns the created diner and optionally links it to an active member of the
   same household.
2. **Given** a diner name already used by an active diner in the household, **When** a member
   creates or renames another diner to the same name with different casing, **Then** the API returns
   `409`.
3. **Given** an archived diner, **When** another diner is created with that name, **Then** the new
   active diner is allowed.
4. **Given** a member link to an active account in another household or to an inactive membership,
   **When** a diner is created or linked, **Then** the API returns `422`.
5. **Given** a member account already linked to another diner in the household, **When** it is linked
   again, **Then** the API returns `409`.
6. **Given** an update with a current `expected_version`, **When** the name or member link changes,
   **Then** the diner is updated and its version increments; a stale version returns `409`.
7. **Given** a diner id from another household, **When** any diner detail mutation or lookup uses
   that id, **Then** the API returns `404`.

### User Story 2: Remember preferences for a diner or the whole household (Priority: P1)

A household member saves durable likes, dislikes, dietary restrictions, goals, or notes for an
individual diner or for the household as a whole. Members can revise or archive each memory without
erasing its audit history.

**Independent Test**: Create a diner-specific restriction and household-level note, update and
archive them, and confirm tenant-scoped reads and the active profile return only current records.

**Acceptance Scenarios**:

1. **Given** an active diner in the household, **When** a member creates a memory with a supported
   kind and trimmed content, **Then** the response contains the diner id and normalized content.
2. **Given** a memory with no diner id, **When** it is created or moved with `diner_id: null`,
   **Then** it is stored at household scope.
3. **Given** content with surrounding whitespace or outside the 1–1000 character trimmed range,
   **When** a memory is created or updated, **Then** valid content is trimmed and invalid content
   returns `422`.
4. **Given** an archived, missing, or foreign diner id, **When** a memory is created or assigned to
   it, **Then** the API returns `404`.
5. **Given** an update with the current `expected_version`, **When** kind, content, or diner scope
   changes, **Then** the memory is updated and its version increments; a stale version returns
   `409`.
6. **Given** a memory for a foreign household, **When** it is retrieved, changed, or archived by id,
   **Then** the API returns `404`.
7. **Given** a diner is archived, **When** the active memory profile is read, **Then** its memories
   remain stored but are absent from the profile.
8. **Given** a memory mutation, **When** its domain event is recorded, **Then** the payload contains
   ids and kind only and never contains memory text or diner display names.
9. **Given** an idempotency key on either create route, **When** an identical request is replayed,
   **Then** the same created row is returned without a duplicate mutation or event.

### User Story 3: Read the household's active memory through REST and MCP (Priority: P1)

A household member or connected agent reads one profile containing active household-level memories
and active diners with their active memories. MCP also offers focused CRUD tools that let an agent
save a lasting preference by diner name or id without confusing one-off meal plans with durable
memory.

**Independent Test**: Read the REST profile and `uribap_get_memory`, verify the same active profile
and household isolation, save by case-insensitive diner name, reject an unknown diner name, then
archive a memory through MCP.

**Acceptance Scenarios**:

1. **Given** active household and diner memories, **When** `GET /memory/profile` is requested,
   **Then** the response has a `household` list and active `diners` with their active memory lists.
2. **Given** archived diners or memories, **When** the profile is requested, **Then** archived
   records are excluded while household-level active memories remain visible.
3. **Given** a member requests a memory listing with a scope, diner filter, archive flag, or limit,
   **When** the query is valid, **Then** only matching household rows are returned in deterministic
   order.
4. **Given** `uribap_remember` receives an active diner name using different letter casing,
   **When** it saves a memory, **Then** it resolves that diner and stores the memory there.
5. **Given** `uribap_remember` receives an unknown diner name, **When** it is invoked, **Then** it
   returns an error instructing the agent to create the diner first.
6. **Given** an authenticated MCP call to `uribap_get_context`, **When** the context is returned,
   **Then** it includes the active household memory profile.
7. **Given** an unauthenticated REST request, **When** any memory endpoint is called, **Then** it
   returns the standard `401` error response.

## Requirements

- **FR-001**: The API MUST model diners separately from user accounts because people who eat in a
  household may not have Uribap accounts.
- **FR-002**: Every diner MUST belong to one household, have a trimmed 1–80 character display name,
  version, timestamps, optional active-member link, and optional archive timestamp.
- **FR-003**: Active diner display names MUST be unique case-insensitively within a household.
  A household member account MUST be linked to at most one diner in that household.
- **FR-004**: A provided member link MUST identify an active membership in the same household;
  invalid links MUST return `422`, and a duplicate link MUST return `409`.
- **FR-005**: All diner and memory reads and mutations MUST be tenant-scoped. Foreign identifiers
  MUST be indistinguishable from absent identifiers and return `404`.
- **FR-006**: Any active household member may read and write diners and memories; owner, admin, and
  member roles have the same permissions for these resources.
- **FR-007**: Diner updates MUST require `expected_version`, apply only supplied fields, and return
  `409` for a stale version. An explicit null `member_user_id` MUST unlink the account.
- **FR-008**: Archiving a diner MUST be a soft archive, preserve its memories, exclude the diner
  and its memories from active profile reads, and return `204` for repeated archive requests.
- **FR-009**: Memory kinds MUST be `like`, `dislike`, `restriction`, `goal`, or `note`.
- **FR-010**: Memory content MUST be trimmed and contain 1–1000 characters after trimming.
- **FR-011**: A memory MAY be household-level (`diner_id: null`) or belong to an active diner in the
  same household; invalid or foreign diner ids MUST return `404`.
- **FR-012**: Memory updates MUST require `expected_version`, apply only supplied fields, allow
  explicit null `diner_id` to move a memory to household scope, and return `409` on stale version.
- **FR-013**: Memory archive MUST be soft; archived memory rows MUST be excluded from active reads.
- **FR-014**: POST `/diners` and POST `/memories` MUST accept the existing optional `Idempotency-Key`
  header and use household-scoped request fingerprints and receipts.
- **FR-015**: Each diner/memory mutation MUST record its specified domain event. Event payloads may
  include ids and memory kind only; memory content and diner display names MUST NOT be logged or
  included in event payloads.
- **FR-016**: REST MUST expose diner and memory list/create/update/archive operations plus the
  active combined profile at the exact paths specified in the API contract.
- **FR-017**: Memory listing MUST support `diner_id`, `scope=all|household|diner`,
  `include_archived`, and `limit` between 1 and 200 with default 200, ordered by household first,
  then diner, kind, and creation time.
- **FR-018**: The profile endpoint MUST contain only active household-level memories and active
  diners with their active memories.
- **FR-019**: MCP MUST expose the specified read and write tools with their required annotations;
  `uribap_remember` MUST resolve `diner_name` case-insensitively and tell the agent to create an
  unknown diner first.
- **FR-020**: `uribap_get_context` MUST include the active memory profile and its description MUST
  mention household memory.
- **FR-021**: All mutation requests and responses, errors, and query parameters MUST be represented
  in the regenerated OpenAPI contract.
- **FR-022**: One reversible Alembic migration MUST create the two tables and indexes/constraints
  after revision `d3c72b91a84f`; the migration chain MUST have one head.

## Assumptions

- An archived diner keeps its `member_user_id`; the unique household/member constraint therefore
  prevents creating a second diner for that account unless the archived diner is explicitly
  unlinked.
- `scope=household` selects only household-level memories; `scope=diner` selects diner memories,
  optionally narrowed by `diner_id`; `scope=all` selects either scope, optionally narrowed by
  `diner_id`. `include_archived=true` includes archived memories and memories attached to archived
  diners in the listing, but the profile endpoint always remains active-only.
- A diner archive increments its version once; archiving an already archived diner is a no-op.
- Empty PATCH bodies beyond `expected_version` are invalid. Archives are permitted for any active
  household member and are idempotent.
- Idempotency receipts reuse the existing household-scoped `MealPlanOperation` storage with
  feature-specific operation names; no extra receipt table is needed.

## Success Criteria

- **SC-001**: All active members can create, list, update, and archive household diners with
  uniqueness, member-link, and optimistic-version guarantees.
- **SC-002**: Memory values are normalized and tenant-isolated; updates, soft archives, and
  household-level reassignment behave as specified.
- **SC-003**: Events record all mutations without storing memory content or diner display names.
- **SC-004**: The active REST profile and MCP memory/context tools return the same household-scoped
  data and honor the specified archive and name-resolution behavior.
- **SC-005**: Idempotency replay, API error shapes, migration round-trip, generated OpenAPI, and all
  new tests pass.
