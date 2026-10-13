# Feature Specification: Ingredient Catalog Pagination

**Feature Branch**: `devin/1791306650-ingredient-pagination`

**Created**: 2026-10-06

**Status**: Ready for implementation

**Input**: User description: Add cursor-based pagination to the ingredient REST and MCP listings so clients can retrieve complete household catalogs larger than the current page limit, while retaining stable order and all existing filters.

## User Scenarios & Testing

### User Story 1 - Retrieve a complete ingredient catalog (Priority: P1)

A household client retrieves every ingredient in a large catalog by requesting successive pages.
Each ingredient appears once and in a stable order, including when several ingredients have the
same normalized name.

**Why this priority**: Missing catalog entries lead downstream clients to show incomplete or
misidentified household data.

**Independent Test**: Create more ingredients than fit in one page, retrieve each page in sequence,
and confirm that the combined results contain every ingredient exactly once and the last page
signals completion.

**Acceptance Scenarios**:

1. **Given** an unchanged catalog with more ingredients than the requested page size, **When** a
   client follows the continuation token, **Then** successive pages contain the full catalog
   without gaps or duplicates.
2. **Given** multiple ingredients with the same normalized name, **When** the catalog is traversed,
   **Then** their order remains deterministic and none are skipped or repeated.
3. **Given** the final page, **When** its pagination information is read, **Then** its continuation
   token is `null`.

### User Story 2 - Continue a filtered ingredient search (Priority: P1)

A household client pages through a search or dimension-filtered catalog without losing the filters
that define the result set. Household and global visibility continue to follow the existing request
options.

**Why this priority**: Catalog pages must represent one consistent filtered result set, rather than
mixing or omitting ingredients as the client continues.

**Independent Test**: Request a filtered first page and continue with the same filters and its
continuation token; verify every returned ingredient matches the filters and the traversal is
complete.

**Acceptance Scenarios**:

1. **Given** a query, dimension, or global-visibility filter, **When** a client requests later pages
   with the same filters, **Then** only matching ingredients appear and no matching ingredient is
   omitted.
2. **Given** a malformed continuation token, **When** the client requests the next page, **Then**
   the service returns a `422` Problem Details response.

### User Story 3 - Traverse the catalog through MCP (Priority: P1)

A connected assistant retrieves a complete ingredient catalog through the existing read-only MCP
listing tool, retaining its current item and count fields while being able to request later pages.

**Why this priority**: MCP clients need the same complete catalog and continuation behavior as REST
clients.

**Independent Test**: List ingredients through MCP with a page size smaller than the catalog, follow
each returned continuation token, and verify the existing fields and full catalog are preserved.

**Acceptance Scenarios**:

1. **Given** a catalog larger than one MCP page, **When** a client follows `next_cursor`, **Then**
   each page returns `items`, `count`, and the next continuation token until the final token is
   `null`.
2. **Given** existing MCP query, dimension, and global-visibility options, **When** the client
   continues a listing, **Then** those options continue to filter every page.

### Edge Cases

- Ingredients that share a normalized name must still have a unique position in the ordered result.
- A malformed, invalidly encoded, or structurally incomplete cursor must return a `422` Problem
  Details response rather than a server error.
- A valid cursor and a filter that yields no further results must produce an empty final page with a
  `null` next cursor.
- Existing household scoping, global-ingredient inclusion, default page size, and maximum page size
  must remain unchanged.

## Requirements

### Functional Requirements

- **FR-001**: Clients MUST be able to request an ingredient listing in pages and continue a listing
  using an optional opaque cursor.
- **FR-002**: Results MUST be ordered ascending by `(Ingredient.normalized_name, Ingredient.id)`
  so ordering remains deterministic across pages when names are equal after normalization.
- **FR-003**: Each page MUST report its effective limit and a next cursor when more matching
  ingredients remain; the next cursor MUST be `null` on the final page.
- **FR-004**: Search, dimension, and global-inclusion filters MUST remain effective on every page
  when supplied with the continuation cursor.
- **FR-005**: Invalid cursors MUST return a `422` Problem Details response.
- **FR-006**: The MCP ingredient-listing tool MUST support an optional cursor and return
  `next_cursor` without removing its existing `items` or `count` fields.
- **FR-007**: Ingredient visibility MUST remain scoped to the active household and the existing
  global-catalog inclusion option.

### Key Entities

- **Ingredient**: A household-owned or global catalog entry with a normalized name and stable
  identifier used to order results.
- **Ingredient page**: A portion of the filtered catalog with its effective limit and an optional
  continuation cursor.
- **Continuation cursor**: An opaque value that lets a client continue from the last returned
  ingredient without choosing or decoding its position.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A client can retrieve a household catalog of 140 ingredients across successive pages
  with no missing or duplicate entries.
- **SC-002**: Traversals containing ingredients with identical normalized names return all entries
  in one deterministic order.
- **SC-003**: Every non-final page provides a continuation value and every exhausted listing
  identifies completion with a `null` value.
- **SC-004**: For an unchanged catalog, search, dimension, and global-inclusion options produce
  the same matching result set throughout a multi-page traversal.
- **SC-005**: REST and MCP clients can complete the same listing while retaining their existing
  response fields.

## Assumptions

- Clients repeat the original filter options when following a continuation cursor; the cursor
  identifies a position and does not replace the filters.
- The existing default and maximum page sizes remain unchanged.
- MCP `count` continues to describe the items returned by that page, as it does today.
- Existing authentication, household scoping, and global ingredient visibility rules are unchanged.
- A multi-page traversal is not a snapshot across concurrent catalog edits; completeness without
  gaps or duplicates is defined for a catalog that remains unchanged during traversal.
