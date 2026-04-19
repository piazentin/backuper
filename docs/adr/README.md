# Architecture decision records

Accepted decisions for **significant** cross-cutting design. **Bar:** document only what is worth maintaining long-term — see **[`AGENTS.md`](../../AGENTS.md#architecture-decision-records-adrs)** (when to write an ADR, optional tooling).

Phased delivery context for SQLite work: [`plans/sqlite-support-assessment.md`](../plans/sqlite-support-assessment.md).

| ADR | Date | Title |
|-----|------|--------|
| [ADR-0001](0001-sqlite-manifest-store.md) | 2026-04-19 | SQLite manifest store layout, WAL, mutual exclusivity with CSV |
| [ADR-0002](0002-version-lifecycle-and-transactions.md) | 2026-04-19 | Version lifecycle (`pending` / `completed`), commit granularity, visibility |
| [ADR-0003](0003-version-ordering-and-most-recent.md) | 2026-04-19 | `list_versions` ordering and `most_recent_version` semantics |
| [ADR-0004](0004-migration-created-at-inference.md) | 2026-04-19 | `created_at` when migrating from CSV (parse vs mtime, collisions, dotfiles) |
