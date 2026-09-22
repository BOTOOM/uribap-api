# Feature Specification: Domain Events, Email Outbox, and Observability

**Feature Branch**: `010-events`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member reviews the recent activity of the household —
  invitations, plan approvals, purchases, preparation outcomes, meal completions —
  through `GET /households/{household_id}/activity`, fed by domain events recorded
  atomically with each mutation.
- **US2 (P1)**: Every mutation that changes household state MUST append a typed
  `domain_event` row in the same transaction, so the activity feed can never drift
  from committed state.
- **US3 (P1)**: Email intents (invitations, future notifications) accumulate in
  `email_outbox_entry`; a dispatcher processes them in order and — while delivery
  is disabled — marks each intent `suppressed` with an auditable
  `email_delivery_intent` record instead of calling SMTP.
- **US4 (P2)**: Operators can re-run the dispatcher safely; dispatch is
  idempotent, batch-limited, and uses `FOR UPDATE SKIP LOCKED` claiming.
- **US5 (P2)**: Observability stays consistent — every event carries `request_id`,
  actor, household, and a scrubbed payload; the dispatcher never leaks template
  bodies containing secrets into logs.

## Requirements

- **FR-001**: `domain_event` MUST be tenant-isolated (`household_id` NOT NULL,
  composite FK where applicable) with `kind`, `actor_user_id`, `aggregate_type`,
  `aggregate_id`, `payload` (JSONB, scrubbed), `request_id`, and `occurred_at`;
  indexed by `(household_id, occurred_at DESC)` for feed reads.
- **FR-002**: A pure domain module MUST own the event-kind catalog
  (`DomainEventKind`), payload-scrubbing rules (denylisted keys: authorization,
  cookie, token, secret, password), and the delivery decision policy —
  `decide_delivery(delivery_enabled)` → `suppressed` when disabled, `send` when
  enabled — plus `next_attempt_delay(attempts)` exponential backoff with a cap.
- **FR-003**: `email_outbox_entry.status` MUST admit a new terminal state
  `suppressed`; the dispatcher MUST claim pending rows with
  `available_at <= now` using `FOR UPDATE SKIP LOCKED`, apply the pure decision,
  write one `email_delivery_intent` per claim (outcome, suppression reason or
  error detail, rendered subject), and update status/attempts atomically.
- **FR-004**: When `email_delivery_enabled` is `false` (default), the dispatcher
  MUST NOT open SMTP connections; suppression MUST NOT retry — suppressed entries
  are terminal. When enabled, failures schedule `available_at` via the backoff
  policy and stay `pending` until `attempts` reaches the cap, then become
  `failed`.
- **FR-005**: Mutation services MUST emit domain events atomically:
  `household.member_added`, `invitation.created`, `invitation.accepted`,
  `invitation.revoked`, `plan.approved`, `plan.reopened`, `shopping.purchased`,
  `preparation.task_completed`, `preparation.task_cancelled`,
  `meal.completed`, `meal.reopened`, `meal.line_corrected`. Payloads MUST carry
  stable aggregate references only (ids, counts, amounts) — never emails, tokens,
  or free-text notes.
- **FR-006**: `GET /households/{household_id}/activity` MUST return a
  cursor-paginated (or offset `page`/`page_size`) newest-first feed of
  `domain_event` for any ACTIVE member of the household, serialized per the
  contract (`ActivityEntry`: `kind`, `occurred_at`, `actor_user_id`,
  `aggregate_type`, `aggregate_id`, `payload`). A summary section MUST include
  outbox counts by status for that household's email intents.
- **FR-007**: Event emission MUST NOT change existing mutation semantics — a
  failed mutation leaves no event; event write failures roll back the mutation.
- **FR-008**: `mailer.py`/`send_outbox_entry` MUST only be reachable when
  `email_delivery_enabled` is `true`; no code path in this phase sends real
  email, and tests MUST assert suppression without network access.

## Success Criteria

- **SC-001**: Completing a plan approval writes `plan.approved` in the same
  transaction; `GET /activity` shows it first for that household and never for
  another household.
- **SC-002**: With delivery disabled, dispatching a pending invitation outbox
  row produces `status = 'suppressed'`, exactly one `email_delivery_intent` with
  outcome `suppressed`, and zero SMTP calls (asserted by monkeypatch).
- **SC-003**: Re-running the dispatcher is a no-op for suppressed/failed rows;
  batch limit is honored.
- **SC-004**: All existing suites remain green; new coverage for event
  emission, dispatcher decisions, feed pagination, and tenant isolation.
