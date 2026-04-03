# Backuper

Very simple backup utility

## Architecture

The CLI runs [`src/backuper`](src/backuper): entrypoints are the composition root, controllers are function-only orchestration with explicit dependencies, `interfaces/` holds ports and shared DTO-style types, and persistence-specific shapes (for example CSV row models in `components/csv_db`) live next to the adapters that use them. For layering, tests, and contribution notes, see **[AGENTS.md](AGENTS.md)**.

## Usage

Examples use `python3 -m backuper`. From a dev checkout after `uv sync --group dev`, `uv run backuper …` is equivalent; with the package installed, the `backuper` console script does the same.

Create a new backup:

```
python3 -m backuper new ~/backup/source/dir ~/backup/destination/dir
```

Update existing backup:

```
python3 -m backuper update ~/backup/source/dir ~/backup/destination/dir
```

Check backup integrity:

```
python3 -m backuper check ~/backup/destination/dir
```

`check` is a fast integrity/existence pass over backup metadata and stored blobs.
If a future deeper validation mode is added (for example full content/hash verification),
it should be exposed as a separate `verify` command rather than changing `check` semantics.

Restore a named version from a backup root into a destination directory (two positionals: backup location, then destination; version via `-v` / `--version` / `-n` / `--name`):

```
python3 -m backuper restore /path/to/backup/root /path/to/restore/into --version backup-version
```


## Development setup

Install [uv](https://docs.astral.sh/uv/), then from the repo root:

```
uv sync --group dev
```

That creates/updates `.venv` from `uv.lock` and installs the project plus dev tools (pytest, Ruff, import-linter). Alternatively run `make sync` (same as `uv sync --group dev`).

## Run tests

```
make test
make unit
make integration
make test-coverage
```

`make test` runs both unit and integration suites; use `make unit` or `make integration` for a single tree.

## Format and lint

Check everything (format, Ruff lint, import boundaries):

```
make lint
```

Apply Ruff formatting and auto-fixes:

```
make lint-fix
```

Format only (writes files):

```
make format
```
