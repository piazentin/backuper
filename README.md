# Backuper

Very simple backup utility

## Architecture

The CLI runs [`backuper/implementation`](backuper/implementation): entrypoints are the composition root, controllers are function-only orchestration with explicit dependencies, `interfaces/` holds ports and shared DTO-style types, and persistence-specific shapes (for example CSV row models in `components/csv_db`) live next to the adapters that use them. For layering, tests, and contribution notes, see **[AGENTS.md](AGENTS.md)**.

## Usage

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

Restore a backup to a location:

```
restore --from /backup/source --to /backup/destination --version backup-version
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
make test-coverage
```

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
