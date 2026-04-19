# Backuper

Very simple backup utility

## Architecture

The CLI runs [`src/backuper`](src/backuper): entrypoints are the composition root, controllers are function-only orchestration with explicit dependencies, `models/` holds shared value types and domain exceptions, `ports/` holds abstract protocols, and persistence-specific shapes (for example CSV row models in `components/csv_db`) live next to the adapters that use them. For layering, tests, and contribution notes, see **[AGENTS.md](AGENTS.md)**.

## Documentation

- **[docs/README.md](docs/README.md)** — index of project docs beyond the README.

## Install and run

Needs **Python 3.11+**.

**Recommended:** install [uv](https://docs.astral.sh/uv/), clone this repository, then from the repo root:

```
uv sync
uv run backuper --help
```

`uv run backuper …` runs the app without activating `.venv`. You can also `source .venv/bin/activate` and run `backuper` or `python -m backuper`.

**Without uv:** from the repo root, `python3 -m venv .venv`, activate the venv, then `pip install -e .` and use that venv’s `backuper` / `python`.

A bare system `python3 -m backuper` fails with `No module named backuper` unless you installed into that interpreter—use `uv run` from the checkout or a venv where the package is installed.

**From a git clone:** you can sync the dev environment and invoke the CLI in one step with **`make backup`** from the repo root. Everything after `backup` is forwarded to `backuper` (after `uv sync --group dev`):

```
make backup new ~/backup/source ~/backup/destination
make backup update ~/backup/source ~/backup/destination
make backup verify-integrity ~/backup/destination
make backup restore /path/to/backup/root /path/to/restore/into --version backup-version
```

Make splits arguments on spaces, so paths **cannot contain spaces** in this form. For Backuper’s own help, use `uv run backuper --help` (after `uv sync` or `make sync`); `make backup --help` shows GNU Make’s help, not the app’s.

## Usage

```
backuper new ~/backup/source/dir ~/backup/destination/dir
```

```
backuper update ~/backup/source/dir ~/backup/destination/dir
```

```
backuper verify-integrity ~/backup/destination/dir
```

Optional flags:

- **Before the subcommand:** `-q` / `--quiet` — less informational logging (stderr).
- **`verify-integrity` only:** `--json` — print one JSON object on stdout: `{"errors": ["…", …]}` (empty list when there are no issues). Suppresses the usual per-line messages and the `No errors found!` line.

**`new` and `update` only — extra ignore rules (without editing the source tree):**

- **`--ignore-pattern` `PATTERN`** (repeatable): one gitignore-style line per flag. All pattern flags are merged **in argv order**, then any `--ignore-file` content (see below).
- **`--ignore-file` `PATH`** (repeatable): UTF-8 file with gitignore-style lines (blank lines and `#` comments skipped, same as on-disk ignore files). **`PATH`** is resolved against the **current working directory** if relative. Files are read **in argv order**; lines from each file are appended after every `--ignore-pattern` line.

Together these form the **user** rule layer: **lower precedence** than `.gitignore` / `.backupignore` in the source tree, so tree rules can still override or narrow what you pass here. Operator guide: **[docs/source-ignores.md](docs/source-ignores.md)**.

`verify-integrity` is a fast integrity/existence pass over backup metadata and stored blobs.

Restore (backup root, then destination; version with `-v` / `--version` / `-n` / `--name`):

```
backuper restore /path/to/backup/root /path/to/restore/into --version backup-version
```

## Version CSV migration

If an existing backup tree still has **legacy** version manifests (short `f` rows without the full seven columns the current reader expects), migrate them **before** running `new`, `update`, `verify-integrity`, or `restore` on that tree. Full rules, blob enrichment, and rollback files (`.bak`) are in **[docs/csv-migration-contract.md](docs/csv-migration-contract.md)**.

From the repository root, use the dev environment so `scripts/` is importable:

```
uv sync --group dev
uv run python -m scripts.migrate_version_csv --help
```

Typical flow: pass the **backup root** (the directory that contains `db/` and `data/` by default). Preview with `--dry-run`, then run again without it to write migrated CSVs (atomic replace; originals preserved as `.bak` per the contract):

```
uv run python -m scripts.migrate_version_csv /path/to/backup/root --dry-run
uv run python -m scripts.migrate_version_csv /path/to/backup/root
```

Use `--db-dir` / `--data-dir` if your layout uses different names than `db` / `data`. Use `--csv path/to/db/version.csv` (repeatable) to migrate specific manifests instead of all `*.csv` under the db directory. Add `-v` / `--verbose` for enrichment warnings on stderr.

Run migration only during a **quiet window** (no concurrent `backuper` commands against the same tree).

**Concurrency:** in general, use a **single writer** per backup root for `new`, `update`, and migration. Version manifests are append-only CSV files without multi-process coordination; the filestore deduplicates identical content hashes on disk but does not make parallel backup jobs safe. See **Concurrency and single-writer expectations** in **[AGENTS.md](AGENTS.md)**.

## Development

- **Environment:** `make sync` or `uv sync --group dev` (app plus pytest, Ruff, import-linter).
- **CLI from checkout:** see **Install and run** → *From a git clone* (`make backup …`).
- **Tests:** `make test` (unit + integration), or `make unit` / `make integration` / `make test-coverage`.
- **Lint:** `make lint` (format, Ruff, import boundaries), `make lint-fix` (with auto-fixes), `make format` (format only).
