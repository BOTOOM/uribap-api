# Quickstart: Deployment Hardening

```bash
# Middleware + env tests
uv run pytest tests/api/test_security_headers.py
uv run pytest tests/unit -k settings

# Full gates
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run alembic check
uv run pip-audit

# Image
docker build -t uribap-api:011-check .
docker run --rm -p 8013:8000 --env-file .env uribap-api:011-check
curl -i http://localhost:8013/api/v1/health/live   # security headers present
curl -I http://localhost:8013/docs                 # docs still reachable
```

Manual flow:

1. `cp .env.example .env` → `docker compose up -d --build` → health green.
2. `curl -i` any API route → `nosniff`, `DENY`, `no-referrer`, `no-store`.
3. Run dispatcher per runbook → suppressed intents, no SMTP traffic.
