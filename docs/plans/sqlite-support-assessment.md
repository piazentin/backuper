# Technical assessment: SQLite manifest support

| | |
|--|--|
| **Created** | 2026-04-18 |
| **Last updated** | 2026-04-19 |

## Purpose

This document assesses adding a **SQLite-backed** implementation of the backup manifest alongside (and eventually instead of) **per-version CSV** files. It is scoped to **phased incremental delivery**: each phase is a shippable increment that can be analysed and broken down into tasks later. It does not prescribe individual tasks.

## Current baseline

- Manifest persistence is expressed through the **`BackupDatabase`** port (`src/backuper/ports/__init__.py`). Controllers depend on that abstraction, not on CSV.
- Today, **`CsvBackupDatabase`** + **`CsvDb`** implement that port using **one CSV file per version** under the configured db directory, with append-oriented writes and documented migration rules for legacy CSV (`docs/csv-migration-contract.md`, `scripts/migrate_version_csv`).
- Composition root: **`create_backup_database`** in `src/backuper/entrypoints/wiring.py` always constructs the CSV stack.

## Goals (assessment drivers)

- **Crash safety:** Manifest updates should be **transactional** where the domain requires atomicity (contrast with append-only CSV and current single-writer assumptions).
- **Transferability:** Single-file (or few-file) store under the backup root, **no separate database server**.
- **Migration:** Existing backup trees that use CSV must have a **supported path** to SQLite without abandoning operator expectations around safety and rollback.
- **Operability:** Plain-text git diff of raw manifests is **not** required; **export/query tooling** and documentation for advanced users are acceptable.

## Non-goals (for this assessment)

- Choosing final PRAGMA values or exact schema DDL (belongs in design work inside Phase 1).
- Replacing or duplicating blob storage under the data directory (only **manifest metadata** is in scope).
- Prescribing a deprecation timeline for CSV writes (optional later phase).

---

## Phase 1 — Design lock-in

**Outcome:** An agreed **persistence model** for SQLite is documented and reviewable: entity boundaries (versions, files, directories), **transaction boundaries** for backup operations, **schema versioning** approach, and **durability posture** (e.g. journal mode, expectations around `synchronous`). Alignment with the existing **`BackupDatabase`** contract and with version-ordering semantics (CSV legacy vs SQLite — see ADRs below) is explicitly called out.

**Accepted ADRs** (under [`docs/adr/`](../adr/)):

| ADR | Date | Topic |
|-----|------|--------|
| [ADR-0001](../adr/0001-sqlite-manifest-store.md) | 2026-04-19 | SQLite file layout, **WAL**, mutual exclusivity with CSV |
| [ADR-0002](../adr/0002-version-lifecycle-and-transactions.md) | 2026-04-19 | **`pending` / `completed`**, commit-per-file, **pending not visible by default**, directory markers |
| [ADR-0003](../adr/0003-version-ordering-and-most-recent.md) | 2026-04-19 | **`list_versions`** lexicographic order, **`most_recent_version`** (SQLite **`created_at`** vs legacy CSV names) |
| [ADR-0004](../adr/0004-migration-created-at-inference.md) | 2026-04-19 | **`created_at`** from parsable **`YYYY-MM-DDTHHMMSS`** stem vs CSV **mtime** (UTC ms), collisions, dotfiles |

Index: [`docs/adr/README.md`](../adr/README.md), [`docs/plans/README.md`](README.md).

**Incremental value:** Stakeholders can approve direction before implementation cost; migration and wiring phases can assume a stable target.

**Later planning:** Schema DDL, PRAGMA tuning, and optional proof-of-concept spikes.

---

## Phase 2 — SQLite adapter (implementation behind the port)

**Outcome:** A **`SqliteBackupDatabase`** (or equivalent name) that **implements `BackupDatabase`**, with tests that validate behaviour **through the port** (not via raw SQL in callers). CSV remains the only wired backend; the new code is **integrable** but not necessarily user-selectable yet.

**Accepted ADRs (Phase 2 finalization):**

| ADR | Date | Topic |
|-----|------|--------|
| [ADR-0005](../adr/0005-sqlite-adapter-contract-and-schema-v1.md) | 2026-04-19 | Port extensions (`most_recent_version`, completion transition), CSV pending temp/finalize behavior, SQLite schema v1 + `user_version` policy, files-then-directories ordering, hash/storage/compression field decisions, deferred async offloading note ([issue #50](https://github.com/piazentin/backuper/issues/50)) |

**Incremental value:** Core persistence logic and test coverage exist in isolation; regressions are caught without touching CLI or migration.

**Later planning:** Map each `BackupDatabase` method to storage operations; define test matrix (parity with CSV behaviour for list/create/add/query paths).

---

## Phase 3 — End-to-end integration for new SQLite-backed trees

**Status:** In progress (core behavior merged; operator-facing follow-ups deferred).

**Outcome:** The composition root now **materialises SQLite or CSV via resolver policy** for a backup root, using on-disk discoverability plus env override semantics. **`new` / `update` / `verify-integrity` / `restore`** are wired with operation context (`write` vs `read`) so backend selection and partial-init handling follow a single policy.

**Done (implemented and covered):**

- Resolver behavior in composition root:
  - SQLite default for new/empty trees.
  - SQLite wins when both SQLite + canonical CSV artifacts exist.
  - `FORCE_CSV_DB=1` forces CSV even when SQLite exists.
  - Canonical CSV detection excludes dot/pending artifacts used in CSV lifecycle transitions.
- Read/write split for partial SQLite initialization:
  - `new` and `update` pass `operation="write"` (repair/migration path allowed by backend implementation).
  - `restore` and `verify-integrity` pass `operation="read"` and fail fast with actionable guidance when SQLite is not read-ready.
- Validation references:
  - Unit resolver matrix and read-path guardrails: [`test/unit/entrypoints/test_wiring.py`](../../test/unit/entrypoints/test_wiring.py)
  - Unit CLI operation-context wiring (`read` vs `write`): [`test/unit/entrypoints/test_cli_runner_resolution_context.py`](../../test/unit/entrypoints/test_cli_runner_resolution_context.py)
  - Integration flow checks (override + partial-init read/write behavior): [`test/integration/test_cli_backend_resolution_integration.py`](../../test/integration/test_cli_backend_resolution_integration.py)

**Accepted ADRs (Phase 3 policy lock-in):**

| ADR | Date | Topic |
|-----|------|--------|
| [ADR-0006](../adr/0006-backend-resolution-policy.md) | 2026-04-19 | Backend precedence (SQLite default, mixed-state selection), `FORCE_CSV_DB=1` override semantics, canonical CSV detection for resolver decisions, and partial SQLite init behavior split by write (`new`/`update`) vs read (`restore`/`verify-integrity`) flows |

**Incremental value:** New backups can opt into SQLite without migration from CSV; validates real workflows before mass migration.

**Deferred from Phase 3 / later planning:**

- CLI/config UX polish beyond current env override contract (for example richer operator controls than `FORCE_CSV_DB=1`).
- Additional operator docs consolidating mixed-manifest diagnostics and recovery runbooks.
- Any policy changes to long-term CSV write posture remain in later phases (see Phase 6 and [ADR-0001](../adr/0001-sqlite-manifest-store.md)).

---

## Phase 4 — Migration from CSV to SQLite

**Outcome:** A **supported migration path** for existing trees: import **canonical** CSV manifests into SQLite, with **dry-run**, **validation**, and **rollback artefacts** consistent with operator expectations established in `docs/csv-migration-contract.md` (adapted for “CSV → SQLite” rather than row-format fixes). Documentation tells operators **when** to migrate and **what** is preserved.

**Incremental value:** Existing deployments can move forward without manual DB editing; reduces long-term dual-format **write** surface if combined with policy from Phase 5.

**Later planning:** Idempotency, partial failure behaviour, and verification steps after migration.

---

## Phase 5 — Operations, observability, and durability hardening

**Outcome:** **Operational** story is complete: documented **SQLite pragmas** and recovery expectations, safe **copy/backup** of the DB file where applicable, and **export or query** guidance (CLI or documented `sqlite3` recipes) for audits and diffs. Performance characteristics (indexes, batching) are validated for realistic manifest sizes.

**Incremental value:** SQLite is **production-grade** for the same roles CSV filled, with clearer crash and inspection behaviour than raw CSV alone.

**Later planning:** Benchmarks, optional convenience commands (`export-manifest`, etc.), and tuning.

---

## Phase 6 (optional) — CSV write posture and long-term maintenance

**Outcome:** Explicit **product decision** encoded in docs and code: e.g. CSV becomes **read-only** for migration only, or remains a **peer write path** for a deprecation period. Test and documentation burden for **dual writers** is bounded by that decision.

**Incremental value:** Predictable maintenance cost; avoids indefinite **full dual-write** unless deliberately chosen.

**Later planning:** Deprecation timeline, removal criteria, and final cleanup of unused paths.

---

## Cross-cutting risks (summary)

| Area | Note |
|------|------|
| **Version ordering** | Legacy CSV: lexicographic “most recent” by name (`AGENTS.md`). SQLite: **`created_at`** + tie-break — see [ADR-0003](../adr/0003-version-ordering-and-most-recent.md) and [ADR-0004](../adr/0004-migration-created-at-inference.md). |
| **Concurrency** | SQLite improves crash semantics; **locking** story (single writer) should remain clear for parallel jobs. |
| **Test suite** | Many tests today assert CSV **file** shape; parity testing should **prefer the port** to avoid permanent 2× file-assertion maintenance. |
| **Migration surface** | A second migration tool alongside `migrate_version_csv` increases **operator cognitive load** unless docs consolidate entry points. |

---

## Document history

| Date | Change |
|------|--------|
| 2026-04-18 | Initial assessment (phased incremental delivery). |
| 2026-04-19 | Phase 1: linked ADR-0001–0004 (SQLite design lock-in). |
| 2026-04-19 | ADRs moved to `docs/adr/`; meta table (created / last updated). |
| 2026-04-19 | Phase 2: linked ADR-0005 (adapter contract + schema v1 decisions). |
| 2026-04-19 | Linked deferred async offload enhancement issue [#50](https://github.com/piazentin/backuper/issues/50) from Phase 2 references. |
| 2026-04-19 | Phase 3: linked ADR-0006 (backend resolution, override, mixed-state, and partial-init read/write policy). |
| 2026-04-19 | Phase 3: added explicit progress status, completed-vs-deferred split, and links to resolver/CLI/integration test coverage. |
