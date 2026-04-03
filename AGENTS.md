# AGENTS.md

This file is the canonical agent and contributor map for this repository; prefer editing it over scattering the same facts elsewhere.

## Entry point

- `python -m backuper` → [`src/backuper/__main__.py`](src/backuper/__main__.py) → [`backuper.entrypoints.main.run_with_args`](src/backuper/entrypoints/main.py) → [`argparser.parse`](src/backuper/entrypoints/argparser.py) → [`run_new` / `run_update` / `run_check` / `run_restore`](src/backuper/entrypoints/cli.py).

## Architecture

- **Commands** live under [`src/backuper`](src/backuper) (package root: `entrypoints/`, `controllers/`, `components/`, `interfaces/`, `commands.py`, `config.py`).
- **Practice**: New features and fixes go in `src/backuper` with tests under `test/implementation`.

## Command naming rubric

- Keep CLI commands verb-first and intent-focused (`new`, `update`, `restore`, `check`).
- `check` is the lightweight integrity/existence pass (current behavior).
- If deeper and more expensive validation is added later, introduce a separate `verify` command rather than changing `check` semantics.

## Tests

- **Environment:** install [uv](https://docs.astral.sh/uv/), then `uv sync --group dev` (or `make sync`) so `make` targets use the locked env.
- **`make test`** — `python3 -m pytest test/` (full tree under `uv run`).
- **`make test-coverage`** — full test tree with coverage across the project (`--cov=.`).

Phase 2 of the layout plan will split **`make unit`** / **`make integration`**; until then use `make test` or narrow with `uv run python -m pytest test/implementation` when you need that scope.

## On-disk and CSV contract

- The on-disk layout and CSV/database rows are defined by the implementation. Integration tests under [`test/implementation/integration/`](test/implementation/integration/) assert expected layouts and rows; see e.g. [`test/implementation/integration/test_new_integration.py`](test/implementation/integration/test_new_integration.py).

## Formatting and lint

- **Ruff** (format + lint) and **import-linter**: `make lint` / `make lint-fix` (see [README.md](README.md)).

## Pull requests

- Always read and follow [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) before opening a PR.
- Keep PR body section headings and order exactly as the template: `Context`, `What`, `How`, `Validation`, `Risks / Rollback`.
- Use `gh pr create` with a body that mirrors the template and includes concrete verification details.

## Implementation layering

- **`entrypoints/`** — Delivery adapters and **composition root** for commands. [`src/backuper/entrypoints/cli.py`](src/backuper/entrypoints/cli.py) is the CLI adapter: it owns stdout UX, basic path/schema validation, and **dependency injection** (constructing concrete adapters and passing them into controllers). There is **no** `src/backuper/cli.py` shim—callers use [`backuper.entrypoints.cli`](src/backuper/entrypoints/cli.py) only. Orchestration in `controllers/` is **swappable delivery**: the same functions should be reusable from another entrypoint later (for example a web API) without duplicating use-case logic.
- **`controllers/`** — Use-case orchestration **only** as **module-level functions** (no orchestration classes). Dependencies are passed **explicitly** as separate parameters; do **not** introduce shared “deps bundle” dataclasses or NamedTuples for hand-off. Where two or more collaborators could be confused, prefer **keyword-only** injected parameters (pattern: `fn(command, *, db=..., filestore=...)`). Controllers depend on **`interfaces`** for port and DTO types; they must not import concrete **`components`** (those are wired in **`entrypoints/`**).
- **`interfaces/`** — Port protocols, shared types, and exceptions ([`backuper.interfaces`](src/backuper/interfaces/__init__.py)). This is the home for **ports**; **`components/`** supply the concrete implementations used at the composition root.
- **`components/`** — Reusable building blocks (e.g. file I/O, CSV DB, analyzer, filestore) that implement **`interfaces`** and remain implementation details behind the composition root.
- **`commands.py`** — Implementation command DTOs only ([`src/backuper/commands.py`](src/backuper/commands.py)).
- **`config.py`** — Shared configuration types and constants ([`src/backuper/config.py`](src/backuper/config.py)).
