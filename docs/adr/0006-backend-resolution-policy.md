# ADR-0006: Backend resolution policy

## Date

2026-04-19

## Status

Accepted

## Context

Runtime selection between CSV and SQLite manifest backends at the composition root must be deterministic for operators and tests, including mixed on-disk states and partially initialized SQLite stores.

Without a locked policy, `new`, `update`, `restore`, and `verify-integrity` could diverge in backend choice or error handling, creating inconsistent behavior and difficult recovery guidance.

## Decision

1. **Backend precedence and default**
   - SQLite is the default backend for new backup trees with no manifest artifacts.
   - When both SQLite and canonical CSV artifacts are present in a backup tree, SQLite is selected.
   - Backend detection is based on file existence under the backup tree.

2. **Environment override**
   - `FORCE_CSV_DB=1` always forces CSV backend selection.
   - This override applies even when SQLite artifacts exist and would otherwise win precedence.

3. **Mixed-manifest behavior**
   - Mixed-state trees (SQLite plus canonical CSV manifests) are resolved by the same precedence rule above: SQLite unless `FORCE_CSV_DB=1`.
   - Canonical CSV detection excludes pending or temporary CSV artifacts used during CSV lifecycle transitions.

4. **Partial SQLite initialization policy**
   - For write flows (`new`, `update`), a partially initialized SQLite backend triggers migration/repair attempts before failing.
   - For read flows (`restore`, `verify-integrity`), partial SQLite initialization fails fast with actionable operator guidance.

5. **Entry-point contract**
   - Command entrypoints stay backend-agnostic.
   - Resolver behavior may depend on operation context (read vs write) so partial-init behavior is flow-correct.

## Consequences

- Backend selection behavior is stable and testable across wiring and command-flow matrices.
- Operators receive deterministic behavior for mixed manifests and explicit override semantics.
- Recovery complexity is constrained: write flows may self-heal; read flows do not mutate state and instead provide guidance.
- Integration docs and tests can reference one normative policy source.

## Related

- [CSV to SQLite migration runbook](../csv-to-sqlite-migration.md)
- [ADR-0001: SQLite manifest store layout and durability](0001-sqlite-manifest-store.md)
- [ADR-0005: SQLite adapter contract and schema v1](0005-sqlite-adapter-contract-and-schema-v1.md)
