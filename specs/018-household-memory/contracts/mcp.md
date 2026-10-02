# Household Memory MCP Contract

All tools run against the household fixed by the authenticated MCP bearer token.

## Tools

- `uribap_get_memory` — READ_ONLY. Description:
  `Read what the household remembers: each diner's likes, dislikes, restrictions and goals plus household-wide notes. Read this before suggesting or planning meals and respect restrictions.`
  Returns the active `HouseholdMemoryProfile`.
- `uribap_add_diner(display_name, member_user_id?, idempotency_key?)` — WRITE. Creates a diner
  using the same validation and event rules as REST. Reusing a key with the same request replays
  the original result; using it for a different request returns an idempotency conflict.
- `uribap_update_diner(diner_id, display_name?, member_user_id?, unlink_member=false,
  expected_version?)` — WRITE. When `expected_version` is omitted, loads and uses the current
  diner version before updating. Omitting `member_user_id` and leaving `unlink_member=false` leaves
  the account link unchanged. Set `unlink_member=true` to remove the link; providing both
  `member_user_id` and `unlink_member=true` is a validation error.
- `uribap_archive_diner(diner_id)` — WRITE. Soft-archives the diner.
- `uribap_remember(content, kind="note", diner_id?, diner_name?, idempotency_key?)` — WRITE. Save
  a durable memory for a diner or the whole household (likes, dislikes, allergies/restrictions,
  goals, notes). Use when the user states a lasting preference; never for one-off plans.
  `diner_id` and `diner_name` cannot both be provided. Names are resolved case-insensitively among
  active household diners. Unknown names return an error telling the agent to create the diner
  first. Omitting both stores household-level memory. Reusing an idempotency key with the same
  request replays the original result; reusing it for a different request returns an idempotency
  conflict. For name-based calls, the fingerprint uses the normalized name rather than the resolved
  diner ID, so a retry returns the original result if the diner was renamed or the name was later
  assigned to someone else.
- `uribap_update_memory(memory_id, content?, kind?, expected_version?)` — WRITE. When
  `expected_version` is omitted, loads and uses the current memory version before updating.
- `uribap_forget_memory(memory_id)` — WRITE. Soft-archives the memory.

All tools use the shared service rules, household isolation, version handling, and privacy-minimized
domain events.

## Context extension

`uribap_get_context` adds `"memory": <HouseholdMemoryProfile>` containing only active household
memories and diners. Append this sentence to its description:

`Includes the household memory (diners' likes, dislikes, restrictions, goals and household notes).`

The MCP transport's tool list is expected to include all new tools.
