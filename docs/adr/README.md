# Architecture decision records

Accepted decisions for **significant** cross-cutting design. **Bar:** document only what is worth maintaining long-term — see **[`AGENTS.md`](../../AGENTS.md#architecture-decision-records-adrs)** (when to write an ADR, optional tooling).

SQLite migration/operator context: [`docs/csv-to-sqlite-migration.md`](../csv-to-sqlite-migration.md).
Scripts import-boundary policy context: see [ADR-0007](0007-scripts-import-boundaries-lint-enforcement.md).

## ADR lifecycle and immutability

This repository treats ADRs as a historical decision log:

- **One ADR = one decision at a point in time.**
- **Accepted** ADRs are effectively **immutable**.
- If a decision changes, write a **new ADR** and mark the old ADR as **`Superseded by ...`**.
- Keep **bidirectional links**:
  - old ADR: `Superseded by ADR-00XX`
  - new ADR: `Supersedes ADR-00YY`
- Do not delete old ADRs; superseded ADRs remain part of project history.

Allowed edits to accepted ADRs are intentionally narrow: typo fixes, broken-link fixes, and status/relationship metadata updates (for example superseded/deprecated markers). Any change that alters meaning should be captured in a new ADR.

References:
- [Martin Fowler — Architecture Decision Record](https://martinfowler.com/bliki/ArchitectureDecisionRecord.html)
- [AWS Prescriptive Guidance — ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html)
- [Michael Nygard (Cognitect) — Documenting Architecture Decisions](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

| ADR | Date | Status | Title |
|-----|------|--------|-------|
| [ADR-0001](0001-sqlite-manifest-store.md) | 2026-04-19 | Accepted | SQLite manifest store layout, WAL, mutual exclusivity with CSV |
| [ADR-0002](0002-version-lifecycle-and-transactions.md) | 2026-04-19 | Accepted | Version lifecycle (`pending` / `completed`), commit granularity, visibility |
| [ADR-0003](0003-version-ordering-and-most-recent.md) | 2026-04-19 | Accepted | `list_versions` ordering and `most_recent_version` semantics |
| [ADR-0004](0004-migration-created-at-inference.md) | 2026-04-19 | Accepted | `created_at` when migrating from CSV (parse vs mtime, collisions, dotfiles) |
| [ADR-0005](0005-sqlite-adapter-contract-and-schema-v1.md) | 2026-04-19 | Accepted | SQLite adapter contract, schema v1 (`user_version`), CSV pending finalize behavior |
| [ADR-0006](0006-backend-resolution-policy.md) | 2026-04-19 | Accepted | Backend precedence, `FORCE_CSV_DB=1`, mixed-manifest rule, partial-init read/write behavior |
| [ADR-0007](0007-scripts-import-boundaries-lint-enforcement.md) | 2026-04-26 | Accepted | Scripts import boundaries enforced in existing lint flow (no extra CI step) |
