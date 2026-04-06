# Backuper

Very simple backup utility

## Architecture

The CLI runs [`src/backuper`](src/backuper): entrypoints are the composition root, controllers are function-only orchestration with explicit dependencies, `interfaces/` holds ports and shared DTO-style types, and persistence-specific shapes (for example CSV row models in `components/csv_db`) live next to the adapters that use them. For layering, tests, and contribution notes, see **[AGENTS.md](AGENTS.md)**.

## Documentation

- **[docs/README.md](docs/README.md)** — index of project docs beyond the README.
- **[docs/tech-debt-roadmap.md](docs/tech-debt-roadmap.md)** — phased technical-debt backlog (dependencies, phases, risks).

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
make backup check ~/backup/destination
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
backuper check ~/backup/destination/dir
```

Optional flags:

- **Before the subcommand:** `-q` / `--quiet` — less informational logging (stderr).
- **`check` only:** `--json` — print one JSON object on stdout: `{"errors": ["…", …]}` (empty list when there are no issues). Suppresses the usual per-line messages and the `No errors found!` line.

`check` is a fast integrity/existence pass over backup metadata and stored blobs. A future deeper validation mode should be a separate `verify` command, not a change to `check`.

Restore (backup root, then destination; version with `-v` / `--version` / `-n` / `--name`):

```
backuper restore /path/to/backup/root /path/to/restore/into --version backup-version
```

## Development

- **Environment:** `make sync` or `uv sync --group dev` (app plus pytest, Ruff, import-linter).
- **CLI from checkout:** see **Install and run** → *From a git clone* (`make backup …`).
- **Tests:** `make test` (unit + integration), or `make unit` / `make integration` / `make test-coverage`.
- **Lint:** `make lint` (format, Ruff, import boundaries), `make lint-fix` (with auto-fixes), `make format` (format only).
