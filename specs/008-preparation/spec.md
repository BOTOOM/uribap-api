# Feature Specification: Preparation Engine

**Feature Branch**: `008-preparation`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member attaches preparation rules (`defrost`, `soak`, `marinate`, `prepare_ahead`) with a lead time and an instruction to a draft recipe version; rules become immutable when the version publishes.
- **US2 (P1)**: When a meal plan is approved, the API derives one preparation task per plan entry per rule, due at the meal's start time minus the rule's lead time, in the household timezone.
- **US3 (P1)**: The member lists preparation tasks ordered by `due_at`, sees overdue and upcoming work, and marks tasks completed or cancelled with optimistic concurrency.
- **US4 (P2)**: The member adds manual preparation tasks (e.g. "soak the beans") with an optional ingredient/amount, and manages them like derived ones.
- **US5 (P2)**: Re-approving a plan keeps derivation idempotent — unchanged entries do not duplicate tasks, and pending derived tasks whose source entry or rule disappeared are cancelled.

## Requirements

- **FR-001**: `recipe_preparation_rule` (existing table) MUST be manageable through the API only while the recipe version is `draft` (`422` otherwise): `POST` create, `DELETE` remove. Rules carry `rule_type`, optional `ingredient_id`, `lead_minutes >= 0`, and `instruction`.
- **FR-002**: `preparation_task` MUST be tenant-isolated by household with a composite FK to `meal_plan_entry`, an enum `status` (`pending`/`completed`/`cancelled`), `origin` (`derived`/`manual`), `task_type` (rule types plus `manual`), `due_at`, integer `version >= 1`, and purchase-style timestamps.
- **FR-003**: Derivation MUST run inside the same transaction as the plan `approve` transition: for every plan entry and every published rule of its recipe version, `due_at = meal_start(planned_date, meal_type, household.timezone) - lead_minutes`. Meal start times are fixed by domain policy: breakfast 08:00, lunch 13:00, snack 17:00, dinner 20:00 local time. An invalid household timezone falls back to UTC.
- **FR-004**: Derived tasks MUST carry a deterministic `fingerprint` hashed from `(meal_plan_entry_id, recipe_preparation_rule_id)`; a partial unique index on `(household_id, fingerprint)` where `origin = 'derived'` MUST prevent duplicates. Re-approval MUST insert only missing fingerprints and MUST cancel `pending` derived tasks of the same plan whose fingerprint is no longer produced. Completed/cancelled tasks are never resurrected or mutated by derivation.
- **FR-005**: Task transitions MUST be `pending → completed` (recording actor and timestamp) and `pending → cancelled`; all other transitions MUST return `409`. Every transition requires `expected_version` and bumps `version`.
- **FR-006**: `POST /preparation-tasks` MUST create a `manual` task: `title` (1–200), optional `instruction`, required aware `due_at`, optional `ingredient_id` (tenant-checked), and optional `amount`/`unit` that MUST be provided together with `amount > 0` and a unit valid for the ingredient dimension.
- **FR-007**: `GET /preparation-tasks` MUST return household tasks ordered by `due_at, id`, with optional `status`, `from`, and `to` filters on `due_at`, including resolved `ingredient_name`, `recipe_name`, and entry `planned_date`/`meal_type` for display.
- **FR-008**: All mutations MUST accept `Idempotency-Key` and persist receipts (`preparation_operation`) with operation + request hash + stored result payload; replay MUST return the stored payload and a different-hash same-key request MUST return `409`.
- **FR-009**: Errors MUST use Problem Details with `401`, `403`, `404`, `409`, and `422` documented in OpenAPI.
- **FR-010**: Preparation MUST NOT write to inventory, shopping, or meal-plan tables; it only reads plans, entries, recipe versions, rules, and ingredients. Email and notifications are out of scope.

## Acceptance

- Approving a plan whose recipe versions define rules creates one pending task per entry/rule with the correct `due_at`.
- Re-approving the same plan creates no duplicates; removing an entry then re-approving cancels its pending derived tasks.
- Completing or cancelling a task flips its status once; a stale `expected_version` returns `409` with no partial write.
- A manual task validates ingredient tenancy and the amount/unit pair.
- Replaying any mutation returns the stored result; a same-key different-body request returns `409`.

## Out of scope

Task reassignment/snoozing, reopening cancelled or completed tasks, notifications/reminders, email delivery, inventory consumption on task completion, unit conversion, and deployment.
