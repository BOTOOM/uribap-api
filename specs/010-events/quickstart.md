# Quickstart: Domain Events and Email Outbox

```bash
# Domain + persistence + service
uv run pytest tests/unit/domain/test_event_policies.py
uv run pytest tests/integration/test_event_schema.py
uv run pytest tests/integration/test_event_service.py

# Contract
uv run pytest tests/api/test_event_routes.py
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check

# Migration
uv run alembic upgrade head
uv run alembic check

# Dispatcher (no email is ever sent while email_delivery_enabled=false)
uv run python -m uribap_api.tools.process_outbox --limit 50
```

Manual flow:

1. Approve a plan or complete a meal → `GET
   /households/{household_id}/activity` lists the event first.
2. Create an invitation → `email_outbox_entry` row pending; run the dispatcher
   → status `suppressed`, one `email_delivery_intent` (`outcome=suppressed`),
   no SMTP traffic.
3. Re-run the dispatcher → no new intents, no status changes.
