# Plan — 013 MCP server

## Architecture

```
┌─────────────┐   Bearer uribap_mcp_*    ┌──────────────────────────────────┐
│  AI agent   │ ───────────────────────▶ │ FastAPI app                      │
│ (Devin etc) │  POST /api/v1/mcp        │  McpAuthMiddleware               │
└─────────────┘                          │   └─ resolve token → principal   │
                                         │  FastMCP streamable_http_app()   │
                                         │   └─ tools → application svcs    │
                                         └──────────────────────────────────┘
```

- `mcp` package added via `uv add "mcp"` (official Python SDK, FastMCP).
- `FastMCP("uribap", stateless_http=True, json_response=True,
  streamable_http_path="/")`; its `streamable_http_app()` is mounted at
  `/api/v1/mcp` behind `McpAuthMiddleware` (pure ASGI).
- `mcp.session_manager.run()` is entered inside the existing FastAPI lifespan
  (`AsyncExitStack`) so the session manager lives with the app.
- Auth: middleware reads `Authorization: Bearer uribap_mcp_*`, hashes with
  SHA-256, loads the token row (active only), resolves `AppUser` (active) +
  `HouseholdMember` (active), stores `McpPrincipal` in `scope["state"]`, bumps
  `last_used_at` at most once per minute per token.
- Tools are sync functions (FastMCP runs them in a threadpool). Each tool opens
  a session from `app.state.session_factory` (captured at build time), resolves
  the membership from the request principal, calls the existing application
  service, and returns structured JSON (Pydantic/dataclass serialization via
  `model_dump`/`asdict` + Decimal/date encoders).
- Optimistic concurrency: tools that mutate read the entity's current `version`
  and pass it as `expected_version`; a 409 surfaces as an actionable error.
- Idempotency: every mutation sends a generated `uuid4` key unless the caller
  supplies `idempotency_key`.

## Files

API:

- `infrastructure/persistence/mcp_models.py` — `McpToken` model.
- `migrations/versions/*_mcp_tokens.py` — table + indexes.
- `mcp/__init__.py`, `mcp/tokens.py` (issue/hash/resolve/revoke service),
  `mcp/auth.py` (ASGI middleware), `mcp/server.py` (FastMCP + tool registration),
  `mcp/tools_*.py` (tools grouped by domain), `mcp/serialization.py`.
- `api/mcp_tokens.py` — REST router (list/create/revoke) + schemas.
- `api/router.py`, `main.py` — wiring.
- `tests/integration/test_mcp*.py`, `tests/unit/test_mcp_tokens.py`.

Web:

- BFF: `app/api/households/[householdId]/mcp-tokens/route.ts` (GET, POST),
  `.../mcp-tokens/[tokenId]/route.ts` (DELETE).
- Page: `app/(app)/settings/agentes/page.tsx` + client components
  (`McpTokenManager`, `McpSetupGuides`), linked from household settings.
- Component test `tests/component/settings/mcp-agents.test.tsx`.

## Tool catalog (prefix `uribap_`)

Read: `get_context`, `list_members`, `list_ingredients`, `get_inventory`,
`list_movements`, `get_forecast`, `list_recipes`, `get_recipe`, `get_plan`,
`get_shopping_list`, `list_preparation_tasks`, `list_completions`, `list_activity`.

Write: `create_ingredient`, `update_ingredient`, `archive_ingredient`,
`register_purchase`, `adjust_lot`, `create_recipe` (draft→lines→publish, inline
ingredient creation by name), `add_plan_entry`, `remove_plan_entry`,
`update_plan_entry`, `transition_plan`, `complete_meal`, `reopen_completion`,
`create_shopping_list`, `purchase_shopping_item`, `transition_shopping_item`,
`transition_shopping_list`, `create_preparation_task`,
`transition_preparation_task`, `update_household`.

## Risks

- FastMCP sub-app lifespan must be entered manually (mounted apps do not run
  their own lifespan) — handled via AsyncExitStack.
- Sync SQLAlchemy sessions inside async tools: declare tools as sync `def`.
- Stateless mode keeps Coolify scaling trivial; SSE still works per-request.
