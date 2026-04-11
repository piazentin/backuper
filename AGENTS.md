# AGENTS.md

This file is the canonical agent and contributor map for this repository; prefer editing it over scattering the same facts elsewhere.

## Entry point

- `python -m backuper` → [`src/backuper/__main__.py`](src/backuper/__main__.py) → [`main()`](src/backuper/entrypoints/cli/main.py) (`sys.exit`) → [`argparser.parse`](src/backuper/entrypoints/cli/argparser.py) (returns a command plus `quiet`) → [`dispatch_command`](src/backuper/entrypoints/cli/main.py) → [`run_new` / `run_update` / `run_verify_integrity` / `run_restore`](src/backuper/entrypoints/cli/runner.py).
- Installed CLI: `[project.scripts]` maps `backuper` to `backuper.entrypoints.cli.main:main` (e.g. `uv run backuper …` after `uv sync`).
- **`main()`** configures the root logger, then dispatches. It prints **`UserFacingError`** messages to stderr (exit **1**, no traceback), logs unexpected exceptions at **ERROR** with full traceback and prints a short generic message to stderr (exit **1**), and re-raises **`SystemExit`** (e.g. `--help`, argparse errors). **`run_with_args()`** parses and dispatches without that outer error boundary (useful for tests or callers that want uncaught exceptions).
- **Parent parser:** `-q` / `--quiet` lowers log verbosity (logging level **WARNING** instead of **INFO**). **`verify-integrity`** accepts **`--json`**: single JSON object on stdout, `{"errors": [...]}`, instead of human-oriented lines (see [`runner._present_verify_integrity_stdout`](src/backuper/entrypoints/cli/runner.py)).

## Architecture

- **Commands** live under [`src/backuper`](src/backuper) (package root: `entrypoints/`, `controllers/`, `components/`, `utils/`, `models/`, `ports/`, `commands.py`, `config.py`).
- **Practice**: New features and fixes go in `src/backuper` with tests under `test/unit` and `test/integration` as appropriate.

## Additional documentation

- **[Tech debt roadmap](docs/tech-debt-roadmap.md)** — phased backlog for refactors and technical debt (also indexed under [docs/README.md](docs/README.md)).
- **CSV migration (operators):** legacy version manifests must be migrated with **`uv run python -m scripts.migrate_version_csv`** before using the current runtime on an existing backup tree; see **[`docs/csv-migration-contract.md`](docs/csv-migration-contract.md)**.

## Command naming rubric

- Keep CLI commands verb-first and intent-focused (`new`, `update`, `restore`, `verify-integrity`).
- `verify-integrity` is the lightweight integrity/existence pass (current behavior).
- If deeper and more expensive validation is added later, introduce a separate command rather than changing `verify-integrity` semantics.

## Tests

- **Environment:** install [uv](https://docs.astral.sh/uv/), then `uv sync --group dev` (or `make sync`) so `make` targets use the locked env.
- **`make backup`** — `uv sync --group dev && uv run backuper …`; pass CLI args as extra goals, e.g. `make backup update /path/to/source /path/to/backup-root` (see [`Makefile`](Makefile)).
- **`make unit`** — `pytest test/unit` (isolated tests: entrypoints, controllers, components) under `uv run`.
- **`make integration`** — `pytest test/integration` (on-disk layout, CSV rows, CLI-style flows).
- **`make test`** — `pytest test/unit test/integration test/scripts` (includes migration script tests under [`test/scripts/`](test/scripts/)).
- **`make test-coverage`** — same scope as `make test` with coverage (`--cov=.`).

Shared fixtures live under [`test/aux/`](test/aux/). Narrow ad hoc runs: `uv run python -m pytest test/unit/...`, `test/integration/...`, or `test/scripts/...`.

## On-disk and CSV contract

- The on-disk layout and CSV/database rows are defined by the implementation. Integration tests under [`test/integration/`](test/integration/) assert expected layouts and rows; see e.g. [`test/integration/test_new_integration.py`](test/integration/test_new_integration.py).
- **Most recent version:** [`CsvDb.get_most_recent_version`](src/backuper/components/csv_db.py) chooses the version whose **name** is the lexicographic maximum among CSV basenames (string order, not numeric or mtime)—see that method’s docstring and [`test/unit/components/test_csv_db.py`](test/unit/components/test_csv_db.py).

### Concurrency and single-writer expectations

- **Single active writer per backup tree.** Run only one of `new`, `update`, or CSV migration against the same backup root at a time. The tool does not coordinate multiple processes; overlapping writers can interleave CSV appends or leave the manifest inconsistent with what was written under `data/`.
- **Version CSVs** ([`CsvDb.insert_dir`](src/backuper/components/csv_db.py) / [`insert_file`](src/backuper/components/csv_db.py)) append rows to the per-version manifest file. There is no cross-process locking or transactional merge—correctness assumes a single writer extending each manifest sequentially.
- **Blob storage** ([`LocalFileStore.put`](src/backuper/components/filestore.py)): content-addressed blobs are published via [`_publish_staged_blob_if_absent`](src/backuper/components/filestore.py). If the destination path already exists (for example another writer finished first for the same hash), the staged copy is removed and the existing blob is kept. That only deduplicates identical-hash content on disk; it does not make concurrent `new`/`update` runs safe. Treat parallel backup jobs against the same tree as unsupported.

## Formatting and lint

- **Ruff** (format + lint) and **import-linter**: `make lint` / `make lint-fix` (see [README.md](README.md)). **Import-linter** contracts in [`pyproject.toml`](pyproject.toml) include: controllers do not import `components` or each other; `utils`, `models`, and `ports` do not import `components`; and a **layers** rule that `backuper.ports` may depend on `backuper.models` only (not the reverse).

## Pull requests

- Always read and follow [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) before opening a PR.
- Keep PR body section headings and order exactly as the template: `Context`, `What`, `How`, `Validation`, `Risks / Rollback`.
- Use `gh pr create` with a body that mirrors the template and includes concrete verification details.

## Implementation layering

- **`entrypoints/`** — Delivery adapters and **composition root** for commands. The CLI delivery adapter lives under [`src/backuper/entrypoints/cli/`](src/backuper/entrypoints/cli/) (`main.py`, `argparser.py`, `runner.py`): it owns stdout UX, basic path/schema validation, and **dependency injection** (constructing concrete adapters and passing them into controllers). Callers should use `backuper.entrypoints.cli.*` modules directly. Orchestration in `controllers/` is **swappable delivery**: the same functions should be reusable from another entrypoint later (for example a web API) without duplicating use-case logic.
- **`controllers/`** — Use-case orchestration **only** as **module-level functions** (no orchestration classes). Dependencies are passed **explicitly** as separate parameters; do **not** introduce shared “deps bundle” dataclasses or NamedTuples for hand-off. Where two or more collaborators could be confused, prefer **keyword-only** injected parameters (pattern: `fn(command, *, db=..., filestore=...)`). Controllers depend on **`models`** and **`ports`** for DTO types and port protocols; they must not import concrete **`components`** (those are wired in **`entrypoints/`**). They may import **`utils/`** when shared helpers are needed.
- **`models/`** — Immutable value types and shared domain exceptions used by **`ports`**, **`controllers`**, and **`components`** ([`backuper.models`](src/backuper/models/__init__.py)). Must not import **`ports`** or **`components`** (import-linter **layers** + forbidden edges).
- **`ports/`** — Abstract port protocols only ([`backuper.ports`](src/backuper/ports/__init__.py)); import **`models`** for signatures only (`ports` → `models`). Must not import **`components`**. **`components`** implement these protocols at the composition root using **`models`** for DTOs.
- **`utils/`** — Shared **pure** helpers (e.g. path normalization, hashing, content-addressed path strings) that depend on **`config`** (and the stdlib) only; they must not import **`components/`** (see import-linter). **`components/`** may import **`utils/`**.
- **`components/`** — Reusable building blocks (e.g. file I/O, CSV DB, analyzer, filestore) that implement **`ports`** using **`models`** and remain implementation details behind the composition root.
- **`commands.py`** — Implementation command DTOs only ([`src/backuper/commands.py`](src/backuper/commands.py)).
- **`config.py`** — Shared configuration types and constants ([`src/backuper/config.py`](src/backuper/config.py)).
