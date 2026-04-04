# Backuper

Very simple backup utility

## Architecture

The CLI runs [`src/backuper`](src/backuper): entrypoints are the composition root, controllers are function-only orchestration with explicit dependencies, `interfaces/` holds ports and shared DTO-style types, and persistence-specific shapes (for example CSV row models in `components/csv_db`) live next to the adapters that use them. For layering, tests, and contribution notes, see **[AGENTS.md](AGENTS.md)**.

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

## Usage

```
backuper new ~/backup/source/dir ~/backup/destination/dir
```

```
backuper update ~/backup/source/dir ~/backup/destination/dir
```

```
backuper check ~/backup/destination/dir
```

`check` is a fast integrity/existence pass over backup metadata and stored blobs. A future deeper validation mode should be a separate `verify` command, not a change to `check`.

Restore (backup root, then destination; version with `-v` / `--version` / `-n` / `--name`):

```
backuper restore /path/to/backup/root /path/to/restore/into --version backup-version
```

## Development

- **Environment:** `make sync` or `uv sync --group dev` (app plus pytest, Ruff, import-linter).
- **Tests:** `make test` (unit + integration), or `make unit` / `make integration` / `make test-coverage`.
- **Lint:** `make lint` (format, Ruff, import boundaries), `make lint-fix` (with auto-fixes), `make format` (format only).
