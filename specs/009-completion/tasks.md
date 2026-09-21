# Tasks: Meal Completion and Reconciliation

## Domain

- T001 Completion policies: state machine, version check, planned-line scaling,
  FEFO allocation, explicit-line validation — with unit tests first.

## Persistence

- T002 `meal_completion`, `meal_completion_line`, `completion_operation` models +
  migration + `uq_meal_completion_household`; schema integration tests for
  constraints, composite FKs, and the partial unique index.

## Service/API

- T003 Complete-entry transaction: approved-plan check, default planned lines or
  validated explicit lines, FEFO deduction writing `meal_consumption` movements,
  receipt + stored payload.
- T004 `GET /meal-completions` filters + `GET /meal-completions/{id}` with resolved
  names; `POST .../lines/{line_id}/correct` (reversal + re-deduction, version bump)
  and `POST .../reopen` (full reversal, `reopened` state).
- T005 Route contract tests, integration tests for
  complete/correct/reopen/replay/insufficient-stock/tenant-isolation, OpenAPI
  export, and full gates.

## Web handoff

- T006 Contract v9 sync; `/plan` completion actions + completed section with
  reopen/correct controls; component/e2e/a11y coverage.
