# Research: Ingredient Catalog Pagination

## Decision: Use a stable composite keyset

Order visible, non-archived household and optional global ingredients by
`(normalized_name, id)`. Apply the existing filters and household/global visibility predicates
before the keyset boundary, then fetch at most `limit + 1` rows.

### Rationale

- The current listing is alphabetic by normalized name, so that remains the primary order.
- Distinct visible rows can share a normalized name when a household entry shadows a global entry.
  The ingredient UUID provides a unique tie-breaker.
- Fetching one extra row answers whether another page exists without a separate count query.
- A composite keyset continues after the last returned item without offset drift when rows are
  inserted before that position.
- Each page evaluates the current catalog; this design does not provide a snapshot across
  concurrent changes between requests.

### Alternatives considered

- **Offset pagination**: Rejected because insertions or removals before an offset can cause skipped
  or repeated ingredients across pages, and large offsets require the database to walk prior rows.
- **Order only by normalized name**: Rejected because distinct household/global ingredients may
  share that value, leaving their relative order unstable at a page boundary.
- **Order only by identifier**: Rejected because it would discard the existing alphabetical
  catalog order.

## Decision: Encode the last returned key as an opaque URL-safe cursor

Encode JSON with the `n` normalized-name value and `id` UUID string using URL-safe Base64. Decode
and validate both values before applying the keyset predicate. Produce the next cursor from the
last row included in the response only when the extra fetched row proves that more results exist.

### Rationale

- The payload contains exactly the composite key needed to continue the stable order.
- URL-safe Base64 works as a query parameter and requires no new dependency or persistent state.
- Treating the value as opaque keeps clients independent of the cursor representation.
- Rejecting malformed or structurally invalid cursor values through `DomainError` yields the
  established Problem Details response instead of an unhandled exception.

### Alternatives considered

- **Return the normalized name or UUID directly**: Rejected because exposing the internal sort key
  would couple clients to implementation details.
- **Add a signed or persisted cursor**: Rejected because the cursor grants no access and the
  household-scoped query remains authoritative; a stateless encoded key is sufficient.

## Decision: Reuse the existing filters and typed page envelope

Keep `query`, `dimension`, `include_global`, and `limit` behavior unchanged. Callers repeat their
filters when requesting a later page. Use the existing `PageInfo` schema for the REST response and
extend the MCP result with `next_cursor`, retaining its current `items` and page-local `count`.

### Rationale

- Applying all predicates on each service invocation keeps filtered pages within the same result
  set and avoids making cursor contents a copy of user-selected filters.
- `PageInfo` already defines the pagination fields used elsewhere in the API.
- Returning the cursor alongside existing MCP fields is an additive contract change.

### Alternatives considered

- **Embed request filters in the cursor**: Rejected because the user-facing design requires filter
  options to remain explicit and the Web caller can preserve its query parameters.
- **Replace MCP `count` with a total catalog count**: Rejected because the contract explicitly
  preserves existing semantics and fields.

## Repository findings

- `list_ingredients` currently applies household/global, archive, query, and dimension predicates,
  then sorts only by `normalized_name` and limits the result.
- `GET /ingredients` currently returns a dictionary for `page_info`; the shared `PageInfo` model
  already provides `next_cursor` and `limit`.
- The MCP `uribap_list_ingredients` tool delegates to the same application service and returns
  `count` and `items`.
- `DomainError` is mapped by the existing API handler to an `application/problem+json` response.
- `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi` regenerates the canonical
  OpenAPI file and accepts `--check`.

## Open questions

None. The feature brief settles page size, sort keys, cursor representation, error status, filter
behavior, and MCP fields.
