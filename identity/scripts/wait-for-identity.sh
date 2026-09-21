#!/usr/bin/env sh
set -eu

issuer_url="${OIDC_ISSUER:-http://localhost:8080}"
mailpit_url="${MAILPIT_URL:-http://localhost:8025}"
api_url="${URIBAP_API_URL:-http://localhost:8010}"
web_url="${URIBAP_WEB_URL:-http://localhost:3000}"

wait_for() {
  name="$1"
  url="$2"
  attempts="${3:-60}"
  i=0
  while [ "$i" -lt "$attempts" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf '%s ready\n' "$name"
      return 0
    fi
    i=$((i + 1))
    sleep 2
done
  printf '%s unavailable: %s\n' "$name" "$url" >&2
  return 1
}

wait_for "ZITADEL" "$issuer_url/debug/ready"
wait_for "ZITADEL discovery" "$issuer_url/.well-known/openid-configuration"
wait_for "ZITADEL JWKS" "$issuer_url/oauth/v2/keys"
wait_for "Mailpit" "$mailpit_url/api/v1/info"
wait_for "Uribap API" "$api_url/api/v1/health/live"
wait_for "Uribap Web" "$web_url/api/health"
