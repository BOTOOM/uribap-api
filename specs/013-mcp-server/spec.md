# 013 — MCP server for AI agents

## Problem

Users want AI agents (Devin, Claude, VS Code Copilot, Cursor, ...) to operate their
household food data — read the pantry, plan meals, register purchases — without going
through the web UI. Today the only machine surface is the OIDC-authenticated REST API,
which agents cannot use because tokens live inside a browser session.

## Scope

### MCP endpoint

- Streamable-HTTP MCP server mounted inside the FastAPI app at
  `POST /api/v1/mcp` (stateless, JSON responses — no sticky sessions, Coolify-friendly).
- One MCP server per deployment; household context comes from the token, not headers.
- Tools cover every user-facing capability:

  - **Read**: household info + members, ingredient catalog, inventory lots + movements,
    demand forecast, recipes + version ingredients, weekly plan + entries, current
    shopping list, preparation tasks, meal completions, household activity.
  - **Write**: create/update/archive ingredient, register purchase lot, adjust lot,
    create + publish recipe (with inline ingredient creation), plan entries
    (add/remove/update), plan transitions (propose/approve/reopen/archive),
    complete/reopen meals, shopping list lifecycle (create, purchase item, skip,
    complete, archive), preparation task lifecycle (create, start, complete, cancel).
- Mutations reuse the existing application services: idempotency keys are generated
  per call (optional caller-supplied key supported) and `expected_version` is fetched
  fresh before each mutation, preserving optimistic concurrency.

### Agent tokens

- New `mcp_token` table: id, household_id, user_id, name, token_prefix,
  token_hash (SHA-256), created_at, last_used_at, revoked_at. No expiry for now.
- Token format `uribap_mcp_<43 urlsafe chars>`; only the hash is stored and the
  plaintext is shown exactly once at creation.
- REST management (regular OIDC session auth):
  - `GET /households/{id}/mcp-tokens` — caller's active tokens.
  - `POST /households/{id}/mcp-tokens` — create (returns plaintext once).
  - `DELETE /households/{id}/mcp-tokens/{token_id}` — revoke own token.
- Revoked/unknown tokens → 401 on the MCP endpoint; `last_used_at` is updated
  on successful authentication.

### Web UI

- Settings section "Agentes (MCP)" lists the MCP endpoint URL, manages tokens
  (create/list/revoke) and shows copy-paste configuration for Devin Desktop,
  Devin Cloud, VS Code, Claude Desktop, Cursor and a generic HTTP client.

## Out of scope

- OAuth 2.1 / dynamic client registration on the MCP endpoint (static bearer only).
- Token scopes or read-only tokens (all tokens inherit the member's permissions).
- Expiring tokens, IP allowlists, per-tool audit log beyond `last_used_at`.

## Acceptance

- `tools/list` exposes the full tool catalog; a live call with a real token reads
  household data and a write tool mutates state exactly like the REST API.
- Integration tests: token lifecycle, 401/403 cases, MCP initialize + tools/list +
  a read tool and a write tool through the mounted app.
- Web section renders token management + setup guides; component tests cover them.
- OpenAPI regenerated (token endpoints) and pinned in web contracts.
