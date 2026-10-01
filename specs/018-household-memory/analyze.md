# Specification Analysis: Household Diners and Memory

**Analyzed**: 2026-10-01
**Inputs**: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/`,
`quickstart.md`, and `.specify/memory/constitution.md`

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
| --- | --- | --- | --- | --- | --- |
| C1 | Constitution alignment | Accepted exception | `plan.md` Model policy exception; Constitution Development Workflow and Model Policy | The required `devin models list --format json` command is unavailable. The feature brief/lead explicitly authorizes using the API `AGENTS.md` model matrix and recording this exception. These model ids are not represented as tool-verified. | Proceed under that explicit authorization; retain this note and do not claim model-list verification. |

No unresolved duplicate, ambiguity, coverage, or artifact-consistency finding was identified. Listing-filter composition, diner-name ordering, archive version behavior, empty-patch handling, and archived member-link retention are stated as assumptions in the spec/research/contracts rather than left implicit.

## Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
| --- | --- | --- | --- |
| FR-001 | Yes | T008, T011, T012 | Diner/account separation and diner CRUD |
| FR-002 | Yes | T002, T008, T010 | Diner fields, trimming, version, and timestamps |
| FR-003 | Yes | T003, T008, T011 | Active case-insensitive name uniqueness and member-link uniqueness |
| FR-004 | Yes | T003, T011 | Active same-household member link validation |
| FR-005 | Yes | T003, T004, T005, T011, T013 | Household-scoped service and REST behavior; MCP uses the authenticated runtime |
| FR-006 | Yes | T005, T011, T013 | Active membership dependency without role-specific restriction |
| FR-007 | Yes | T003, T011, T012 | Presence-aware expected-version updates |
| FR-008 | Yes | T003, T011, T012 | Soft diner archive, retained memories, repeated archive |
| FR-009 | Yes | T002, T008, T010 | Memory-kind enum and schema validation |
| FR-010 | Yes | T002, T010 | Trimmed 1–1000 character content |
| FR-011 | Yes | T004, T013, T014 | Household/diner scope and active-diner validation |
| FR-012 | Yes | T004, T013, T014 | Versioned memory update and explicit null reassignment |
| FR-013 | Yes | T004, T013, T014 | Memory soft archive and active filtering |
| FR-014 | Yes | T003, T004, T011, T013 | Household-scoped create receipts, replay, and fingerprinting |
| FR-015 | Yes | T003, T004, T011, T013 | Mutation events and event-payload privacy |
| FR-016 | Yes | T005, T012, T014, T015 | Diner/memory REST routes and combined profile |
| FR-017 | Yes | T004, T014 | Scope, diner, archive, limit, and deterministic ordering |
| FR-018 | Yes | T004, T015 | Active-only profile contents |
| FR-019 | Yes | T006, T016 | MCP tool list, annotations, memory writing, name resolution |
| FR-020 | Yes | T006, T017 | Context profile and appended description sentence |
| FR-021 | Yes | T005, T018 | Standard error shapes and generated OpenAPI |
| FR-022 | Yes | T007, T009, T019 | Reversible migration, requested predecessor, and one-head verification |
| SC-001 | Yes | T003, T011, T012 | Diner create/list/update/archive |
| SC-002 | Yes | T004, T013, T014 | Normalization, tenant isolation, update, archive, scope |
| SC-003 | Yes | T003, T004, T011, T013 | Mutation events exclude memory text and diner names |
| SC-004 | Yes | T005, T006, T015, T016, T017 | Consistent household-scoped REST and MCP profile |
| SC-005 | Yes | T003, T004, T005, T007, T018, T019 | Idempotency, API errors, migration, OpenAPI, tests |

## Constitution Alignment Issues

- **Model verification**: The literal constitution requires identifiers verified by
  `devin models list --format json` and says to stop if unavailable. The command is unavailable in
  this environment. The lead-authorized exception is recorded in `plan.md`: use the API
  `AGENTS.md` matrix identifiers, disclose that they are not tool-verified, and proceed. This is an
  accepted policy exception, not a claim of successful tool verification.
- **Other principles**: No identified conflicts. The plan preserves deterministic services,
  tenant isolation, test-first implementation, canonical OpenAPI, existing modular-monolith
  infrastructure, and reversible Alembic operations.

## Unmapped Tasks

None. T001 records feature setup; T002–T007 cover the test-first gate; T008–T017 map to the three
user stories; T018–T020 cover contract generation, verification, and convergence.

## Metrics

- **Functional requirements**: 22
- **Buildable success criteria**: 5
- **Total traced requirements**: 27
- **Total tasks**: 20
- **Coverage**: 100% (27/27 requirements have one or more task mappings)
- **Unresolved ambiguity count**: 0
- **Duplication count**: 0
- **Unresolved critical issues**: 0 (one lead-authorized model-verification exception is documented)

## Next Actions

Proceed to implementation with the feature's test-first gate. Keep the approved model exception
visible in the plan and convergence record. The MVP increment is User Story 1 (diner profiles);
US2 depends on the shared table/schema foundation, and US3 depends on the completed memory service.

No remediation edits are required before implementation. The model-verification exception must
remain reported as an exception rather than as a verified model-list result.
