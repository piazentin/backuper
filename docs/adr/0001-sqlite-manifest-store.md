# ADR-0001: SQLite manifest store layout and durability

## Date

2026-04-19

## Status

Accepted

## Context

The backup manifest is moving from per-version CSV files to SQLite under the backup root ([`docs/plans/sqlite-support-assessment.md`](../plans/sqlite-support-assessment.md)). We need a clear on-disk story: where the database lives, how it coexists with legacy CSV, and how durability options interact with Python tooling and operator workflows.

## Decision

1. **Canonical database file**  
   The SQLite manifest lives at a single agreed path under the backup tree (exact filename reserved for design/schema work; e.g. under the same logical `db/` directory used for CSV today). Operators think in terms of **one primary database file** for the manifest.

2. **WAL journal mode**  
   Use **WAL** (`PRAGMA journal_mode=WAL`) as the default durability mode for the manifest database. WAL is implemented by the SQLite engine; Python’s standard library **`sqlite3`** and common async wrappers use the same engine and support WAL via `PRAGMA` like any other SQLite client.

3. **Companion files**  
   WAL implies **`*.sqlite-wal`** and **`*.sqlite-shm`** may exist while the database is in use or before checkpoint. Documentation and operator guidance must treat safe backup/copy as **checkpoint**, **`Connection.backup`**, or the **`sqlite3` CLI** `.backup` — not as “copy only the main file” without qualification.

4. **Mutual exclusivity with CSV**  
   A given backup root uses **either** CSV manifests **or** the SQLite manifest, **never both as active writers**. Discovery rules (implementation detail) choose one backend; no dual-write of manifest data in the same tree.

## Consequences

- Phase 5 ops docs must spell out **WAL companion files** and **safe backup** procedures.
- “Single file under the backup root” in product language means **one logical manifest database**; physically, WAL may add short-lived companion files — this must be clear for support and scripting.

## Related

- [sqlite-support-assessment.md](../plans/sqlite-support-assessment.md)
- [ADR-0002: Version lifecycle and transactions](0002-version-lifecycle-and-transactions.md)
