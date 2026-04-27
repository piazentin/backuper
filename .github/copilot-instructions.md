# Copilot Review Instructions

## Review Philosophy
- Provide only high-confidence findings with clear evidence from the diff.
- Prioritize runtime correctness, safety, and security before maintainability or polish.
- Prefer concise, actionable comments that explain impact and suggested direction.
- Avoid speculative concerns without a concrete failure mode.

## Severity Taxonomy
Use this fixed taxonomy:

- `critical`: security vulnerabilities, data loss/corruption risk, correctness breakage, concurrency hazards, contract violations.
- `important`: reliability/maintainability issues with likely behavioral impact, non-critical architecture drift.
- `low`: clarity, documentation, or polish suggestions without direct runtime/safety risk.

Only emit a severity when confidence is high and impact is plausible.

## Priority Areas
Focus review effort on:

- Manifest/database integrity and persistence behavior (`SQLite`, migrations, verification flows).
- Concurrency and single-writer guarantees (destination lock, race conditions, non-atomic flows).
- Backup/restore correctness (blob addressing, path handling, source-ignore semantics, destructive operations).
- CLI behavior contracts and error handling (exit codes, `UserFacingError` boundaries, operator-visible output).
- Import-boundary and layering violations that can create runtime coupling or reliability drift.

## CI Context (Already Gated)
CI already enforces substantial quality gates; do not duplicate these unless there is a clear diff-specific failure risk:

- Lint/format/type/import contracts via `make lint` (`ruff format --check`, `ruff check`, `mypy`, `lint-imports`).
- Test matrix via `make test` on Python 3.11/3.12/3.13.
- Coverage gate via `make test-coverage` (threshold enforced in CI).

Treat style-only or mechanically lint-covered issues as suppressed by default.

## Skip List
Do not comment on:

- Pure formatting/style nits already handled by Ruff.
- Generic "add tests" remarks unless a concrete untested failure path is introduced.
- Architecture/style purity suggestions without behavioral or reliability impact.
- Rephrasing/copy-edit suggestions unless text can cause operator misuse or incorrect operation.
- Issues already guaranteed by CI/import-linter and not newly bypassed by the change.

## Response Format
When you do comment, use this compact format:

1. `severity`: `critical|important|low`
2. `issue`: one-sentence problem statement
3. `evidence`: specific file/symbol/diff behavior
4. `impact`: concrete runtime or operator consequence
5. `suggestion`: minimal actionable fix direction

Keep comments short and avoid repeating repository policy text.

## Silence Rules
Stay silent when:

- Confidence is low or evidence is incomplete.
- The concern is speculative and lacks a concrete failure scenario.
- The issue is already covered by CI/rules and the diff does not bypass those gates.
- The comment would be stylistic/editorial only and not operationally meaningful.

Prefer no comment over low-signal noise.

## Repo-Specific Context
Applies to this repository's Python CLI backup utility.

Architecture and boundary expectations:

- Delivery/composition lives in `entrypoints`; orchestration in `controllers`; adapters in `components`.
- `controllers` must not import `components`; respect import-linter contracts.
- `ports` define abstractions; `models` define shared value types/exceptions; preserve layering.
- Runtime/operator contracts are documented in `AGENTS.md` and `docs/*` (especially manifest/migration/ignore behavior).

When in doubt, favor preserving documented operational contracts and backward-compatible CLI behavior.
