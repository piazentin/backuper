# CSV to SQLite migration runbook

Operator guide for migrating an existing backup tree from per-version CSV manifests to `manifest.sqlite3`.

Use this runbook only during a maintenance window with a single active writer for the target backup root.

## Prerequisites

- Backup tree layout is available (by default `<backup_root>/db` and `<backup_root>/data`).
- You can run project scripts with `uv run` from the repository root.
- You have a filesystem backup/snapshot of the backup root before migration.

## End-to-end flow

Run these phases in order.

### 1) Verify and normalize CSV manifests (legacy to canonical)

If manifests may contain legacy row shapes, run `migrate_version_csv` first.

```bash
uv run python -m scripts.migrate_version_csv /path/to/backup/root --dry-run
uv run python -m scripts.migrate_version_csv /path/to/backup/root
```

Use `--db-dir`, `--data-dir`, and repeatable `--csv` when your tree differs from defaults or you need a subset run.

Contract details: [`docs/csv-migration-contract.md`](csv-migration-contract.md).

### 2) Migrate canonical CSV manifests to SQLite

Preview first:

```bash
uv run python -m scripts.migrate_manifest_csv_to_sqlite /path/to/backup/root --dry-run
```

Apply:

```bash
uv run python -m scripts.migrate_manifest_csv_to_sqlite /path/to/backup/root
```

Important behavior:

- If `<backup_root>/<db_dir>/manifest.sqlite3` already exists, apply refuses by default.
- Use `--force` only when you intentionally want a rebuild from CSV inputs.
- After success, migrated CSV files are moved to an archive directory under `db/` (for rollback and audit).

### 3) Post-migration validation

Run at least integrity validation:

```bash
uv run backuper verify-integrity /path/to/backup/root
```

Recommended: run one representative restore verification too.

```bash
uv run backuper restore /path/to/backup/root /tmp/restore-check --version <version-name>
```

SQLite manifest operations and troubleshooting: [`docs/sqlite-manifest-operations.md`](sqlite-manifest-operations.md).

## Mixed-state and backend resolution notes

- When both SQLite artifacts and canonical CSV manifests are present, runtime resolution prefers SQLite.
- `FORCE_CSV_DB=1` forces CSV resolution for troubleshooting or controlled rollback workflows.
- Keep mixed-state windows short and documented during maintenance actions.

Reference policy: [ADR-0006](adr/0006-backend-resolution-policy.md).

## Rollback / recovery

If you must return to CSV-backed operation:

1. Stop active backup commands.
2. Copy archived CSV files from the migration archive directory back to `<backup_root>/<db_dir>/`.
3. Move or remove `manifest.sqlite3` (and companion `-wal` / `-shm` files if present).
4. Optionally set `FORCE_CSV_DB=1` for explicit CSV backend selection during recovery.
5. Re-run `verify-integrity` and a restore smoke test before resuming normal operations.

For deep SQLite operational guidance, see [`docs/sqlite-manifest-operations.md`](sqlite-manifest-operations.md).
