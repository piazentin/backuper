# SQLite-only runtime: remove CSV DB from main code

Drop the CSV manifest adapter from the shipped `backuper` package. **Migration guidance** (which script to run, in what order, links to runbooks) lives **only in documentation and under `scripts/`**. **`src/backuper` must not** name migration modules, link to docs, or prescribe operator remediation beyond factual state (“no usable manifest database”, “required tables missing”, etc.).

Migration tooling may keep importing shared pieces (`SqliteDb`, config helpers, path utilities, a small parse error type). Scripts do not import `csv_db` today.

## Locked decisions

- **Legacy CSV-only trees:** If the backup would have relied on per-version CSV manifests under `db/` without a usable SQLite manifest, **`operation="read"` and `operation="write"` both fail fast** with the same generic policy (no CSV runtime, no silent `update` that creates SQLite beside old CSVs).
- **Stray `db/*.csv` next to a valid SQLite file:** **Silent** at runtime; describe in **documentation** if operators might be confused by leftovers.
- **`index_status`:** **Remove** from `create_backup_database`, CLI runner, and tests (it only served CSV index build progress).
- **Naming and dead code:** Prefer **clean long-term names** (e.g. rename **`MalformedBackupCsvError`** to a manifest-neutral exception used by scripts and parsers). No intentional dead modules left in `src/` after the cutover milestone merges.
- **Changelog:** Out of scope (no changelog file yet).

---

## Milestone 1 — SQLite-only cutover (`src/` + tests, CI green)

**Objective:** After this milestone merges, **`main` has no CSV DB adapter**, wiring is SQLite-only, legacy CSV-only backups get a **generic** usage error, and the full test suite passes. No migration how-to strings inside `src/`.

**Activities**

- **`wiring.py`:** Remove CSV backend selection, `FORCE_CSV_DB`, and helpers only used for CSV selection. Resolve backend to SQLite only; keep or tighten SQLite read probing as needed.
- **Legacy guard:** When canonical per-version CSV manifests exist under `db/` (use a **single, explicit discovery rule** implemented in wiring—define it here in the PR, no obligation to preserve old CSV integration edge cases) **and** there is no usable SQLite manifest for that backup root, raise **`CliUsageError`** with a **short, generic** message (e.g. manifest database missing or not usable). **Do not** mention `scripts.…`, `uv run`, or paths under `docs/`.
- **Remove `index_status`** from `create_backup_database`, `entrypoints/cli/runner.py`, and any callers/tests.
- **Delete** `src/backuper/components/csv_db.py`. Remove **`CsvDbConfig`** from `config.py` if unused. Clean **`pyproject.toml`** (e.g. Ruff per-file ignores for `csv_db`).
- **Tests and fixtures:** Replace all uses of `CsvDb` / `CsvBackupDatabase` / `CsvDbConfig` with SQLite adapters or `create_backup_database`. Move or duplicate tiny **`_DirEntry` / `_StoredFile`** shapes into **test-local** helpers for `test/aux/fixtures.py`. Remove or replace CSV-only unit test files. Update **`test/scripts/integration/test_migrate_version_csv_integration.py`** to assert via SQLite (or `BackupDatabase`), not `CsvDb`.
- **Naming:** Rename **`MalformedBackupCsvError`** (and exports) to a **neutral** name (e.g. malformed manifest row / manifest parse error—pick one term and use it consistently in `models`, `scripts`, and tests). Update **`verify_integrity`** (and any other) user-facing strings in **`src/`** so they do not imply “CSV” as the live manifest format.

**Exit criteria**

- No `backuper.components.csv_db` (and no shipped CSV DB types) under `src/` or `test/`.
- Lint, typecheck, import-linter, and tests green on **`main`** after merge.
- Grep over **`src/backuper`** shows no migration script names, no `docs/` references, and no “run `python -m …`” style remediation in errors.

---

## Milestone 2 — Documentation and operator runbooks

**Objective:** Contributors and operators learn the full story from **docs and scripts**, not from `src/`.

**Activities**

- Update **README**, **AGENTS.md**, **docs/csv-migration-contract.md**, **docs/csv-to-sqlite-migration.md**, **docs/sqlite-manifest-operations.md** (as applicable), and **ADR 0003** (or add a short ADR) so they describe **SQLite-only CLI** and place **step-by-step migration** (including **`migrate_version_csv`** vs **`migrate_manifest_csv_to_sqlite`** when relevant) here only.
- Document **silent** behavior for stray CSV files next to SQLite if that matters for support.

**Exit criteria**

- A new reader cannot infer that the CLI still uses per-version CSV as the runtime manifest.
- Runbooks contain the remediation that Milestone 1 intentionally omits from code.

---

## Milestone 3 (optional) — Stricter script import policy

**Objective:** If “isolated scripts” should be enforced, not only described: limit what `scripts/` may import from `backuper` (e.g. `models`, `utils`, `components.sqlite_db`).

**Activities:** Import-linter contract and/or **AGENTS.md** note; optional CI check.

**Exit criteria:** Policy is written; if lint is added, CI enforces it.

---

## Merge discipline

- **No milestone may merge in a state where CI is red** or where `src/` still contains an unreachable CSV DB adapter “for later.”
- **Milestone 1** is intentionally **one coherent cutover** (wiring + tests + deletion + naming cleanup) so `main` never sits between “CSV removed from wiring” and “tests still import `csv_db`.”
- **Milestone 2** can land in the same release train immediately after, or in parallel if it does not depend on renamed symbols (if doc links mention old exception names, update them in M2).

## Risk

Backups with **only** CSV manifests under `db/` will **stop working** with the CLI until operators follow **Milestone 2** runbooks. This is an intentional breaking change; note it in release communication you already use (no dedicated changelog file).
