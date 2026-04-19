# Phase 4 tech discovery: CSV → SQLite manifest migration

| | |
|--|--|
| **Created** | 2026-04-19 |
| **Last updated** | 2026-04-19 |
| **Parent plan** | [sqlite-support-assessment.md](sqlite-support-assessment.md) (Phase 4) |

## Purpose

This document registers **tech discovery**, **research notes**, and **decisions** for **Phase 4 — migration from CSV to SQLite**. Interactive open questions are **resolved** (see **Decisions recorded**). It does not prescribe implementation tasks; those belong in later breakdown work.

**Scope:** Operator-facing migration of **canonical** per-version CSV manifests into the SQLite manifest store, with expectations aligned to [`docs/csv-migration-contract.md`](../csv-migration-contract.md) (dry-run / apply posture, rollback mindset) adapted for **CSV → SQLite** rather than legacy row-shape fixes.

**Out of scope here:** Final DDL, PRAGMA values, or runtime code changes (see ADRs and the adapter).

---

## Authoritative references

| Resource | Role |
|----------|------|
| [sqlite-support-assessment.md](sqlite-support-assessment.md) | Phase 4 outcome and incremental value |
| [docs/csv-migration-contract.md](../csv-migration-contract.md) | Canonical CSV contract, legacy→canonical tool (`scripts/migrate_version_csv`), atomic replace, `.bak` rollback pattern, maintenance-window guidance |
| [ADR-0001](../adr/0001-sqlite-manifest-store.md) | SQLite layout, WAL, **mutual exclusivity** with CSV as active writers |
| [ADR-0002](../adr/0002-version-lifecycle-and-transactions.md) | `pending` / `completed`, default visibility |
| [ADR-0003](../adr/0003-version-ordering-and-most-recent.md) | `list_versions`, `most_recent_version`, transition semantics |
| [ADR-0004](../adr/0004-migration-created-at-inference.md) | **`created_at`** inference when importing from CSV (parsable stem vs mtime, collisions, dotfiles) |
| [ADR-0005](../adr/0005-sqlite-adapter-contract-and-schema-v1.md) | Port contract, schema v1 |
| [ADR-0006](../adr/0006-backend-resolution-policy.md) | Backend resolution when **both** SQLite and canonical CSV exist on disk (`FORCE_CSV_DB`, partial init read vs write) |
| [docs/sqlite-manifest-operations.md](../sqlite-manifest-operations.md) | Operator semantics for SQLite files, WAL companions, safe copy |

---

## Research summary

### What Phase 4 must deliver (from the assessment)

- A **supported** path for **existing** backup trees: import **canonical** CSV into SQLite.
- **Dry-run**, **validation**, and **rollback artefacts** consistent with operator expectations established for CSV migration (adapted for format migration).
- Documentation for **when** to migrate and **what** is preserved.
- **Later planning** (explicitly deferred in the assessment): idempotency, partial failure behaviour, verification steps after migration.

### Cross-cutting constraints

- **Version ordering:** CSV legacy “most recent” uses lexicographic version names; SQLite uses **`created_at`** plus tie-break ([ADR-0003](../adr/0003-version-ordering-and-most-recent.md), [ADR-0004](../adr/0004-migration-created-at-inference.md)). Migration must populate SQLite consistently with ADR-0004.
- **Resolver:** If both SQLite and canonical CSV exist, **SQLite wins** unless `FORCE_CSV_DB=1` ([ADR-0006](../adr/0006-backend-resolution-policy.md)). Post-migration on-disk layout and operator mental model must be documented so “leftover CSV” behaviour is predictable.
- **Two migration entry points:** `migrate_version_csv` (row-shape / canonicalization) vs future CSV→SQLite tooling increases **operator cognitive load** unless docs consolidate **order of operations** and **when to use which** (see [sqlite-support-assessment.md](sqlite-support-assessment.md) cross-cutting risks).
- **Concurrency:** [`docs/csv-migration-contract.md`](../csv-migration-contract.md) treats concurrent locks as **out of scope for Phase 4.1**; quiet-window and “do not run alongside runtime commands” remain **documented operational policy**.

---

## Decisions recorded

| Decision | Notes |
|----------|--------|
| **Standalone script module** | CSV→SQLite migration is a **fully separated** maintenance entry point under **`scripts/`**, analogous to **`scripts/migrate_version_csv`** (independent source, `python -m scripts.<module>` style, not wired through the normal CLI composition root). |
| **Canonical CSV precondition (documented only)** | Migration **requires** manifests to match the **current canonical CSV contract** (i.e. “CSV in latest version” of the contract). Operators with **legacy** rows must run **`migrate_version_csv`** first. This requirement is **documentation-only** for Phase 4: the CSV→SQLite tool focuses on **canonical → SQLite** without duplicating full legacy parsing as a second implementation path. |
| **Non-canonical / invalid CSV handling (hybrid)** | Do **not** reimplement legacy row-shape migration in the CSV→SQLite tool. **Reuse** the same canonical parsing path the runtime uses for CSV (or a thin shared validator derived from it) so there is a **single** definition of “canonical.” On detectable non-canonical or unparseable rows, **fail fast** with a stable, operator-facing error that names the manifest (and row where practical) and points to **`migrate_version_csv`**. |
| **Per-version CSV after successful import (archive directory)** | After a **successful** import, **do not** leave active copies of migrated manifests beside the SQLite DB. Move or copy them into an **archive subdirectory** under the manifest area (e.g. `db/csv-archive/<run-timestamp>/` or `db/_migrated_from_csv/<run-id>/`), preserving **original filenames** inside that folder so rollback is “copy files back out of the archive” (and adjust SQLite / `FORCE_CSV_DB` per [ADR-0006](../adr/0006-backend-resolution-policy.md) as documented). Exact directory naming is an implementation detail; document the layout and rollback in the operator runbook. |
| **`pending` vs `completed` for imported versions** | CSV has no explicit `pending` state. **Default:** versions that **parse completely** through the canonical pipeline map to **`completed`** ([ADR-0002](../adr/0002-version-lifecycle-and-transactions.md)). **Structurally incomplete** manifests (e.g. unparseable tail, truncated last row, clear CSV/parse abort) → **fail that version** (or the run—define in implementation) with an operator-facing error rather than inserting a misleading `completed` row. **Soft suspicion** (e.g. empty file, odd row counts): **warn** prominently; do not invent `pending` from weak heuristics unless criteria are documented and testable. If structural incompleteness cannot be defined reliably for a case, prefer **import as `completed` + warning** and point operators to **`verify-integrity` / restore** checks per maintenance guidance. |
| **Atomic publish / failure model** | Build the SQLite manifest in a **staging path** (separate file under `db/` or a temp name), using **one transaction or batched commits** inside that file as implementation prefers. **Publish** by **atomic replace** (rename/swap) to the live manifest filename only after the full logical import succeeds, so operators never see a **partial live** DB picked up by the resolver ([ADR-0006](../adr/0006-backend-resolution-policy.md)). On failure before publish: **remove** the staging DB (or leave it under a clear suffix e.g. `.failed` for inspection—pick one and document). **Resume** across runs is not required for Phase 4 unless later planning expands it; re-run is a full rebuild of the staging file. |
| **Idempotency / repeat runs** | If the **published** manifest SQLite file **already exists**, a second **apply** **refuses** with a non-zero exit and a clear message (path, how to intentionally re-run). Provide an explicit **`--force`** (name TBD) that rebuilds from the current CSV inputs through staging and atomic publish. **Manual CSV edits after import** are **out of band**: post-migration **SQLite is source of truth**; re-import requires **`--force`** and a coherent CSV set (e.g. restore manifests from `csv-archive/` into the expected locations first). **No-op / reconcile** by comparing DB to CSV is **not** required for Phase 4. |
| **Post-migrate validation strategy** | **`verify-integrity`** and optionally **`restore`** (per [csv-migration-contract](../csv-migration-contract.md) maintenance guidance) remain the **authoritative** checks after apply. The migrator adds **light** logging only: e.g. per-version **row/file counts** and **warnings** for **`created_at`** collisions or tie-breaks already computed during import ([ADR-0004](../adr/0004-migration-created-at-inference.md)). Do **not** duplicate full integrity or blob-existence verification inside the migration tool for Phase 4. |
| **Published DB: checkpoint / copy-friendly handoff** | After successful build (staging and/or immediately after publish), run a **WAL checkpoint that truncates** the log (e.g. `PRAGMA wal_checkpoint(TRUNCATE)` or equivalent) so the **published** manifest DB is **self-contained** in the main file for filesystem copy/backup, aligned with [ADR-0001](../adr/0001-sqlite-manifest-store.md) and [sqlite-manifest-operations](../sqlite-manifest-operations.md). The runtime may recreate **`-wal`/`-shm`** on next open; migration completes in a defined, copy-friendly state. |
| **Operator documentation** | Provide a **single operator-facing runbook** (exact path left to implementation: e.g. extend [csv-migration-contract](../csv-migration-contract.md), add a dedicated doc under `docs/`, or a Phase 4 section in [sqlite-manifest-operations](../sqlite-manifest-operations.md)) that sequences: legacy CSV → **`migrate_version_csv`** (dry-run / apply) when needed → **CSV→SQLite** (dry-run / apply) → **`verify-integrity`** / optional **`restore`**, with **troubleshooting** for mixed-state trees, **`FORCE_CSV_DB`**, CSV archive layout, and rollback. The CSV→SQLite script’s **`--help`** must **point to** that runbook and stay aligned with the same steps. |

---

## Related

- Phase 6 (CSV write posture long-term) is **canceled** in [sqlite-support-assessment.md](sqlite-support-assessment.md); Phase 4 should not assume a future product decision beyond existing ADR-0001 / ADR-0006 rules.

---

## Document history

| Date | Change |
|------|--------|
| 2026-04-19 | Initial tech discovery: research, open questions, recorded decisions. |
| 2026-04-19 | Recorded decisions: hybrid canonical validation / fail-fast UX; archive-directory fate for migrated per-version CSV after success. |
| 2026-04-19 | Recorded decision: `pending` vs `completed` mapping for CSV-only trees (complete parse → `completed`; structural incompleteness → fail; soft suspicion → warn; fallback warn + operational verification). |
| 2026-04-19 | Recorded decision: staging SQLite + atomic publish; remove or `.failed` staging on error; resume not required for Phase 4. |
| 2026-04-19 | Recorded decision: idempotency—refuse second apply if published DB exists; `--force` for intentional rebuild; SQLite as post-migration truth. |
| 2026-04-19 | Recorded decision: validation—operational `verify-integrity` / `restore` authoritative; migrator logs light counts + `created_at` collision/tie-break warnings only. |
| 2026-04-19 | Recorded decision: WAL `TRUNCATE` checkpoint after successful publish for copy-friendly manifest DB handoff. |
| 2026-04-19 | Recorded decision: single operator runbook + script `--help` aligned; interactive tech-discovery open questions complete. |
