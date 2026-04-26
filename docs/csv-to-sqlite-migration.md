# CSV to SQLite migration runbook

Operator guide for migrating an existing backup tree from per-version CSV manifests to `manifest.sqlite3`.

Use this runbook only during a maintenance window with a single active writer for the target backup root.
Migration scripts are tooling-only entrypoints: they reuse selected shared `backuper` modules but are intentionally isolated from runtime CLI orchestration layers.

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

## Runtime policy after migration

- Runtime CLI commands (`new`, `update`, `verify-integrity`, `restore`) operate on the SQLite manifest backend.
- A CSV-only backup tree is not runtime-usable until migration completes.
- Keep migration windows short and documented, then run post-migration validation before resuming normal operations.

Current runtime policy source: [`docs/sqlite-manifest-operations.md`](sqlite-manifest-operations.md) (Runtime policy section). Script boundary rationale: [ADR-0007](adr/0007-scripts-import-boundaries-lint-enforcement.md).

## Rollback / recovery

If migration or validation fails and you need to roll back:

1. Stop active backup commands.
2. Copy archived CSV files from the migration archive directory back to `<backup_root>/<db_dir>/`.
3. Move or remove `manifest.sqlite3` (and companion `-wal` / `-shm` files if present).
4. Keep the tree in maintenance mode until remediation is complete.
5. In CSV-only rollback state, validate rollback inputs with migration tooling (`migrate_version_csv --dry-run`) and your filesystem snapshot checks.
6. If you want runtime validation (`verify-integrity` / restore smoke test), rebuild SQLite first by re-running this runbook (phase 2, then phase 3) before resuming normal operations.

After rollback, treat the tree as pre-migration input and re-run the scripted flow during the next maintenance window. Do not resume regular runtime commands against a CSV-only tree.

For deep SQLite operational guidance, see [`docs/sqlite-manifest-operations.md`](sqlite-manifest-operations.md).
