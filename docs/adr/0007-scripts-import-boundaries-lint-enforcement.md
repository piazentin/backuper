# ADR-0007: Scripts import boundaries enforced in lint

## Date

2026-04-26

## Status

Accepted

## Context

Migration tooling under `scripts/` must remain isolated from runtime orchestration internals in `src/backuper` while still reusing stable shared helpers.

The project already has a lint path in local development and CI (`make lint`), including import-linter. Adding a separate CI workflow step/job for this policy would duplicate existing enforcement plumbing.

## Decision

1. **Scripts import guidance**
   - `scripts/` should prefer stable shared modules such as `backuper.models`, `backuper.utils`, `backuper.config`, and selected SQLite manifest adapter wiring under `backuper.components.sqlite_db`.
   - This list documents the intended architecture for review, but it is not fully enforced by import-linter today.

2. **Disallowed coupling**
   - `scripts/` must not import runtime orchestration and delivery layers such as `backuper.entrypoints` and `backuper.controllers`.
   - Other runtime-only internals remain discouraged by architecture review, but are not yet covered by the current lint contract.

3. **Enforcement path**
   - Enforce the current import boundary through import-linter contracts executed by the existing `make lint` target.
   - The current machine-checked contract blocks imports from `backuper.entrypoints` and `backuper.controllers`; broader guidance in this ADR remains review-only until additional contracts are added.
   - Do not introduce a dedicated CI step/job for this policy; CI continues to enforce the current import-linter contract through the existing lint job.

## Consequences

- The currently enforced script/runtime boundary is explicit and machine-checked without adding pipeline complexity.
- Contributors get one enforcement entrypoint locally and in CI (`make lint`).
- Policy evolution remains centralized in lint contracts and architecture docs instead of scattered ad hoc checks.

## Related

- [AGENTS.md scripts import boundaries guidance](../../AGENTS.md#scripts-import-boundaries)
- [ADR-0006: Backend resolution policy](0006-backend-resolution-policy.md)
