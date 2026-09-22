# Quickstart: Meal Completion

```bash
# Domain + persistence + service
uv run pytest tests/unit/test_completion_policies.py
uv run pytest tests/integration/test_completion_schema.py
uv run pytest tests/integration/test_completion_service.py

# Contract
uv run pytest tests/api/test_completion_routes.py
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check

# Migration
uv run alembic upgrade head
uv run alembic check
```

Manual flow:

1. `POST /plans/{plan_id}/entries/{entry_id}/complete` on an approved entry →
   `201` with lines; verify `inventory_movement` rows (`meal_consumption`) and
   reduced lot balances.
2. `POST /meal-completions/{id}/lines/{line_id}/correct` with a different
   `actual_amount` → reversal + new consumption movements.
3. `POST /meal-completions/{id}/reopen` → lots restored; completing the entry
   again succeeds.
