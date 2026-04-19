# ADR-0005: SQLite adapter contract and schema v1

## Date

2026-04-19

## Status

Accepted

## Context

The existing ADR set defines high-level direction for SQLite manifest storage, lifecycle semantics, ordering, and migration timestamp inference. This ADR defines the concrete adapter contract and schema details for `SqliteBackupDatabase` behind `BackupDatabase`, while CSV remains a supported backend.

This document captures stable architectural decisions that tests, migration work, and operator documentation can treat as normative behavior.

## Decision

1. **Port extensions and lifecycle hand-off**
   - `BackupDatabase` includes `most_recent_version()` and explicit completion transition (`complete_version(name)`).
   - Backends create versions as `pending` and expose them as `completed` only after controller success-path finalization.
   - Backup orchestration marks completion after stream/write success; failure paths do not transition.

2. **CSV pending compatibility**
   - CSV creates a temporary pending manifest file at version creation time.
   - Normal CSV listing APIs exclude pending temp files from `list_versions()` and `most_recent_version()`.
   - On success, pending temp file is atomically renamed to canonical final CSV name.
   - On failure/abort, pending temp file is retained for operator inspection and potential recovery.

3. **SQLite schema v1 and migration policy**
   - SQLite manifest lives under the backup tree `db/` directory.
   - Connection bootstrap enables:
     - `PRAGMA foreign_keys=ON`
     - `PRAGMA journal_mode=WAL`
   - Schema versioning uses `PRAGMA user_version` with forward-only migrations.
   - Schema v1 contains:
     - `versions(name, state, created_at)`
     - `version_files(id INTEGER PRIMARY KEY, version_name FK, restore_path, hash_algorithm, hash_digest, storage_location, compression, size, mtime)`
     - `version_directories(id INTEGER PRIMARY KEY, version_name FK, restore_path)`
   - Required indexes support:
     - `most_recent_version` lookup on completed rows and timestamp ordering
     - hash lookup by `(hash_algorithm, hash_digest)`
     - metadata lookup by `(restore_path, mtime, size)` semantics
     - efficient per-version listing

4. **Behavioral contract for the SQLite adapter**
   - `create_version`: inserts `pending` with `created_at`.
   - `complete_version`: transitions `pending` to `completed`.
   - `list_versions`: returns completed versions in lexicographic ascending order.
   - `most_recent_version`: selects completed max by `created_at`, tie-break by lexicographically greater version name.
   - `add_file`: writes to `version_files` (file rows) or `version_directories` (directory markers), commit-per-row strategy.
   - `list_files`: returns file entries first, then directory markers (preserves current CSV-visible behavior).
   - `get_files_by_hash`: matches `(hash_algorithm, hash_digest)`.
   - `get_files_by_metadata`: matches path + mtime + size.

5. **Field model choices**
   - Hash persistence uses split fields: `hash_algorithm` and `hash_digest`.
   - Storage path field is named `storage_location`.
   - Compression is stored as algorithm string (for example `none`, `zip`), with compatibility mapping where current model surfaces still use boolean semantics.

6. **I/O posture (deferred enhancement)**
   - Blocking DB I/O remains acceptable under the current architecture.
   - Async offloading (`asyncio.to_thread` / executor strategy) is deferred to follow-up GitHub enhancement issue [#50](https://github.com/piazentin/backuper/issues/50) and remains out of scope for this decision.

## Consequences

- Port contract tests can run against CSV and SQLite with one shared behavior matrix while documenting backend-specific differences explicitly.
- Migration and integration work can rely on stable schema/user_version and lifecycle semantics without redefining adapter behavior.
- Operator recovery expectations include retained CSV pending artifacts and hidden pending visibility by default.
- Follow-up issue [#50](https://github.com/piazentin/backuper/issues/50) tracks event-loop fairness and connection/thread-ownership risks before async DB offloading is introduced.

## Related

- [ADR-0001: SQLite manifest store layout and durability](0001-sqlite-manifest-store.md)
- [ADR-0002: Version lifecycle, transactions, and default visibility](0002-version-lifecycle-and-transactions.md)
- [ADR-0003: `list_versions` ordering and `most_recent_version`](0003-version-ordering-and-most-recent.md)
- [ADR-0004: `created_at` inference when migrating CSV -> SQLite](0004-migration-created-at-inference.md)
- [SQLite support assessment (phased)](../plans/sqlite-support-assessment.md)
