# Tasks — 013

- [x] `uv add mcp` + lockfile (mcp 1.x FastMCP)
- [x] `McpToken` persistence model + Alembic migration `f2b8d4e6a917`
- [x] `mcp/tokens.py` service (issue, sha256 hash, resolve→principal, revoke, list, last_used_at)
- [x] REST router `api/mcp_tokens.py` (`GET/POST/DELETE /households/{id}/mcp-tokens`) + wiring in `api/router.py`
- [x] `mcp/auth.py` ASGI bearer middleware → `McpPrincipal` in scope (401 + WWW-Authenticate)
- [x] `mcp/server.py` FastMCP stateless + `mcp/serialization.py` JSON encoder (Decimal→"1500", UUID, dates)
- [x] 32 tools: lectura (contexto, miembros, actividad, ingredientes, recetas, inventario, movimientos, forecast, plan, compra, preparación, completions) + escritura (hogar, ingrediente CRUD, receta+líneas+publish, lotes, ajustes, plan entries, transiciones, compras, tareas, completions)
- [x] `main.py`: Route directa en `/api/v1/mcp` (sin 307 de Mount) + dispatch a app MCP construida por lifespan (session manager single-use)
- [x] Idempotencia en `create_lot` (misma dedup que `apply_adjustment`: fingerprint + 409)
- [x] Tests unit/integración: token hash/resolve/revoke/scoping/last_used (7), transporte MCP initialize/tools/list/call/401/errores (3), REST rutas 401+OpenAPI (2)
- [x] `tests/integration/test_migrations.py` head → `f2b8d4e6a917`
- [x] Web BFF routes (`/api/households/[id]/mcp-tokens[/tokenId]`) + `/settings/agentes` (gestión de tokens + guías Devin Desktop/Cloud, VS Code, Claude, otros) + nav (desktop/móvil) + fix `serverApiFetch` en 204
- [x] Web component test (6 casos)
- [x] Live: token creado desde UI → handshake + `uribap_get_context` (Casa Demo) → revocado → 401; aislamiento entre hogares verificado; idempotencia replay verificada
- [x] Converge + commit
