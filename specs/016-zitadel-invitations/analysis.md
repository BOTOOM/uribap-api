# Analysis — 016 ZITADEL household invitations

## Clarify gate

The product and API decisions are settled in the user brief; no clarification is
required before implementation.

## Readiness review

- The feature uses the existing household invitation and outbox records; no schema
  change or migration is necessary.
- New-account and existing-account paths are distinct and have explicit delivery
  outcomes.
- Delivery is attempted only after the invitation has been committed, so a provider
  failure does not remove the invitation.
- Directory exceptions and delivery logs have an explicit data-minimization boundary.
- Both invitation acceptance routes will share the post-lock service path, preventing
  differences in membership, audit, and event effects.
- Verified-email checks, normalized matching, row locking, and hidden cross-email
  not-found behavior are testable in the API and PostgreSQL integration suites.
- Web contract synchronization is sequenced after the API branch is pushed, so its
  metadata can reference the exact API commit.
- External identity-provider and browser-based acceptance checks are intentionally
  out of scope; the directory uses MockTransport and Web convergence will disclose
  the missing authenticated-browser/ZITADEL validation.

## Decision

**Ready for implementation.** No unresolved product decisions or migration
requirements block the feature.
