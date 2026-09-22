# Research: Deployment Hardening

- Starlette middleware ordering: `add_middleware` wraps previously added
  middleware; registering `SecurityHeadersMiddleware` last makes it outermost,
  so Problem Details error responses also carry headers.
- Swagger/Scalar docs load external CDN assets; a strict CSP on docs paths
  breaks them — scope restrictive headers to `/api/v1` and leave docs
  functional (they remain an operator surface behind auth deployment anyway).
- HSTS (`Strict-Transport-Security`) on a plain-HTTP origin is a foot-gun for
  local deployments; Coolify/Traefik terminates TLS and can add it there —
  documented, not app-set.
- Coolify deploys the repository Dockerfile directly; migrations run as an
  explicit release command before switching traffic — the image `CMD` only
  starts uvicorn.
- `email_delivery_enabled` already defaults to `False` in `Settings`; the gap
  is documentation in `.env.example` and the runbook.
