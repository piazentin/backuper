# AGENTS.md

This file is the canonical agent and contributor map for this repository; prefer editing it over scattering the same facts elsewhere.

## Entry point

- `python -m backuper` → [`backuper/__main__.py`](backuper/__main__.py) → [`backuper.legacy.cli.run_with_args`](backuper/legacy/cli/__init__.py).

## Target architecture and migration

- **Goal**: Implement every CLI command under [`backuper/implementation`](backuper/implementation). [`backuper/legacy`](backuper/legacy) is deprecated and will be removed once migration is complete.
- **Practice**: Default new features and fixes to `implementation` and tests under `test/implementation`. Do not entrench or unnecessarily expand legacy.

## Current command routing

- **`new`**: Runs [`backuper.implementation.entrypoints.cli.run_new`](backuper/implementation/entrypoints/cli.py) unless legacy is forced or used as fallback (see below).
- **`BACKUPER_NEW_USE_LEGACY`**: When this environment variable is set to a truthy value (`1`, `true`, `yes`, `on`, case-insensitive), `new` uses only the legacy path ([`backuper/legacy/cli/__init__.py`](backuper/legacy/cli/__init__.py)).
- **Fallback**: If `run_new` raises, the CLI prints a warning to stderr and retries with legacy `new` (runtime safety net until the implementation is stable).
- **`update`**: Runs [`backuper.implementation.entrypoints.cli.run_update`](backuper/implementation/entrypoints/cli.py) unless legacy is forced or used as fallback (see below).
- **`BACKUPER_UPDATE_USE_LEGACY`**: When this environment variable is set to a truthy value (`1`, `true`, `yes`, `on`, case-insensitive), `update` uses only the legacy path ([`backuper/legacy/cli/__init__.py`](backuper/legacy/cli/__init__.py)).
- **Fallback**: If `run_update` raises, the CLI prints a warning to stderr and retries with legacy `update`.
- **`check`**: Runs [`backuper.implementation.entrypoints.cli.run_check`](backuper/implementation/entrypoints/cli.py) unless legacy is forced or used as fallback (see below).
- **`BACKUPER_CHECK_USE_LEGACY`**: When this environment variable is set to a truthy value (`1`, `true`, `yes`, `on`, case-insensitive), `check` uses only the legacy path ([`backuper/legacy/cli/__init__.py`](backuper/legacy/cli/__init__.py)).
- **Fallback**: If `run_check` raises, the CLI prints a warning to stderr and retries with legacy `check`.
- **`restore`**: Still dispatched to legacy in [`backuper/legacy/cli/__init__.py`](backuper/legacy/cli/__init__.py) until migrated.

## Command naming rubric

- Keep CLI commands verb-first and intent-focused (`new`, `update`, `restore`, `check`).
- `check` is the lightweight integrity/existence pass (current behavior).
- If deeper and more expensive validation is added later, introduce a separate `verify` command rather than changing `check` semantics.

## Tests

- **`make test`** — `python3 -m pytest test/` (full tree, including legacy tests).
- **`make test-implementation`** — `python3 -m pytest test/implementation` (narrow suite; default for implementation work).
- **`make test-coverage`** — full test tree with coverage across the project (`--cov=.`).

## On-disk and CSV parity

- Legacy defines the on-disk contract (layout and CSV/database rows). Integration tests under [`test/implementation/integration/`](test/implementation/integration/) assert parity where formats matter; see e.g. [`test/implementation/integration/test_new_parity.py`](test/implementation/integration/test_new_parity.py) (implementation vs legacy expectations and cross-readability).

## Formatting and lint

- **Ruff** (format + lint) and **import-linter**: `make lint` / `make lint-fix` (see [README.md](README.md)).

## Pull requests

- Always read and follow [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) before opening a PR.
- Keep PR body section headings and order exactly as the template: `Context`, `What`, `How`, `Validation`, `Risks / Rollback`.
- Use `gh pr create` with a body that mirrors the template and includes concrete verification details.

## Implementation layering

- **`entrypoints/`** — Delivery adapters and **composition root** for migrated commands. [`backuper/implementation/entrypoints/cli.py`](backuper/implementation/entrypoints/cli.py) is the CLI adapter: it owns stdout UX, basic path/schema validation, and **dependency injection** (constructing concrete adapters and passing them into controllers). There is **no** `backuper/implementation/cli.py` shim—callers use [`backuper.implementation.entrypoints.cli`](backuper/implementation/entrypoints/cli.py) only. Orchestration in `controllers/` is **swappable delivery**: the same functions should be reusable from another entrypoint later (for example a web API) without duplicating use-case logic.
- **`controllers/`** — Use-case orchestration **only** as **module-level functions** (no orchestration classes). Dependencies are passed **explicitly** as separate parameters; do **not** introduce shared “deps bundle” dataclasses or NamedTuples for hand-off. Where two or more collaborators could be confused, prefer **keyword-only** injected parameters (pattern: `fn(command, *, db=..., filestore=...)`).
- **`components/`** — Reusable building blocks (e.g. file I/O, CSV DB, analyzer, filestore) behind interfaces where appropriate.
- **`commands.py`** — Implementation command DTOs only ([`backuper/implementation/commands.py`](backuper/implementation/commands.py)). Mapping from legacy parsed commands to these types happens **only** at the legacy CLI boundary ([`backuper/legacy/cli`](backuper/legacy/cli/__init__.py) via [`impl_mapping.py`](backuper/legacy/cli/impl_mapping.py)); `implementation` must not import legacy command types.
- **`config.py`** — Shared configuration types and constants ([`backuper/implementation/config.py`](backuper/implementation/config.py)).
