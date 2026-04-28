# Search Feature PRD (v1)

## 1. Context

The project currently provides backup lifecycle commands (`new`, `update`, `restore`, `verify-integrity`) and stores file-version metadata in the manifest backend (SQLite in current runtime). Operators can create and update versions, but there is no first-class search command to discover where a file/path appears over time.

Search is a high-priority usability and operations gap. It should be prioritized early so users can inspect historical presence and change behavior without ad hoc manifest inspection.

## 2. Problem Statement

Users need a reliable CLI workflow to answer questions such as:
- "In which versions did this path exist?"
- "When did this file start/stop appearing?"
- "Which versions actually changed this file?"

Without a dedicated command, these questions require manual querying or custom scripts, creating friction and inconsistent outcomes.

## 3. Goals

- Deliver a `search` CLI command in v1 as an early roadmap priority.
- Return results ordered by version age, newest first.
- Default to presence mode: include all versions where a file/path is present.
- Support optional changed-only mode via `--changed-only`.
- Support practical filtering beyond exact-only matching:
  - Substring query matching (default).
  - Optional glob matching with `--glob`.
  - Optional path scoping with `--path-prefix`.
- Provide `--ignore-case` in v1, applying consistently to query, glob, and prefix matching.
- Keep implementation aligned with architecture layering (`entrypoints` -> `controllers` -> `ports` -> `components`).

## 4. Non-Goals

- Full-text content search inside file payloads (search is path-based in v1).
- Advanced ranking/scoring (ordering is deterministic by version recency).
- Regex mode in v1.
- Any API/server surface (CLI only for now).
- Major manifest schema redesign (v1 should operate on existing version + file linkage model).

## 5. User Stories

- As an operator, I can search for a filename fragment and see all versions where it exists.
- As an operator, I can scope search to a subtree (prefix) when a backup root has many files.
- As an operator, I can use glob patterns for familiar shell-style matching.
- As an operator, I can request changed-only results to audit historical modifications.
- As an operator, I can run case-insensitive matching to avoid case-guessing failures.

## 6. Functional Requirements

1. Add a new CLI subcommand: `search`.
2. Inputs:
   - Positional query string (substring mode default), or `--glob` pattern mode.
   - Optional `--path-prefix` to limit candidate paths.
   - Optional `--changed-only` to return only versions where the path changed.
   - Optional `--ignore-case` to perform case-insensitive matching for all applicable filters.
3. Default behavior (no `--changed-only`): presence mode across versions.
4. Output ordering: newest version first.
5. Output should contain enough metadata to identify version and matched path(s) in stable machine-parsable lines (exact rendering details remain implementation-level).
6. Validation errors should follow existing CLI error handling patterns (`UserFacingError` style user-readable stderr in entrypoint boundary).

## 7. Matching and Ordering Semantics

### Matching

- **Default matching mode:** substring match against normalized manifest path.
- **Glob mode:** if `--glob` is provided, treat query as a glob pattern and match against normalized path.
- **Path prefix filter:** if `--path-prefix` is provided, only evaluate paths under that prefix.
- **Case sensitivity:**
  - Default is case-sensitive.
  - With `--ignore-case`, query, glob pattern, and prefix comparison all use case-insensitive comparisons.

### Ordering

- Primary ordering is by version age, newest first.
- If additional deterministic tie-break is needed, use version identifier descending within equal timestamps.

## 8. CLI Contract (v1)

### Proposed command shape

`backuper search <backup-root> <query> [--glob] [--path-prefix <prefix>] [--changed-only] [--ignore-case]`

### Notes

- `<query>` is interpreted as substring by default.
- `--glob` switches interpretation of `<query>` to glob pattern.
- `--changed-only` changes semantic mode from presence to changed-only.
- `--ignore-case` applies to all match checks (query/glob/prefix).

### Examples

- Presence search by substring:
  - `backuper search /data/backups "report.csv"`
- Presence search by substring with subtree filter:
  - `backuper search /data/backups "report" --path-prefix "finance/2025/"`
- Presence search with case-insensitive matching:
  - `backuper search /data/backups "readme" --ignore-case`
- Glob search:
  - `backuper search /data/backups "*.parquet" --glob`
- Glob + prefix + ignore-case:
  - `backuper search /data/backups "**/daily/*.csv" --glob --path-prefix "exports/" --ignore-case`
- Changed-only audit:
  - `backuper search /data/backups "customer.db" --changed-only`

## 9. Data Model and Query Strategy

v1 should use existing manifest concepts:
- `versions`: version identity + chronology metadata.
- `version_files`: file-path presence and per-version linkage.

No schema change is assumed for v1.

### Presence mode (default) pseudo-SQL

```sql
SELECT v.version_id, v.created_at, vf.path
FROM versions v
JOIN version_files vf ON vf.version_id = v.version_id
WHERE match(vf.path, :query_or_glob, :is_glob, :ignore_case)
  AND prefix_match(vf.path, :path_prefix, :ignore_case)
ORDER BY v.created_at DESC, v.version_id DESC;
```

`match(...)` is conceptual: implementation can map to SQLite `LIKE`/`GLOB` or in-process filtering, as long as behavior matches contract.

### Changed-only mode pseudo-algorithm

```
for each matched path P:
  iterate versions newest -> oldest (or oldest -> newest with post-sort)
  compare P's file identity in current version vs previous version
  emit version when P is added/removed/modified (identity differs)
sort emitted rows by version recency (newest first)
```

Conceptual file identity can be hash/blob-reference plus metadata fields needed to detect meaningful change per existing manifest semantics.

### Layering alignment and likely touched modules

- **`entrypoints/cli/argparser.py`**: add `search` parser and flags.
- **`entrypoints/cli/runner.py`**: wire command handling and stdout presentation.
- **`controllers/`** (new module/function): orchestrate search behavior and mode selection.
- **`ports/`**: extend database/search protocol for query operations.
- **`components/sqlite_db/`**: implement search data access against SQLite manifest.
- **`commands.py`**: add command DTO for search inputs.

This document proposes behavior only; it does not claim implementation exists yet.

## 10. Edge Cases and Open Decisions

- Empty query string: reject as user-facing validation error (proposed).
- Query containing literal glob metacharacters in substring mode: treat literally unless `--glob` is set.
- Prefix normalization/trailing slash handling: should follow existing path normalization utilities.
- Duplicate path rows per version: define whether output should be distinct by `(version, path)` (proposed: yes).
- Changed-only baseline for first version: clarify whether initial appearance counts as "changed" (proposed: yes, as an add event).
- Deletions in changed-only mode: clarify display representation when path disappears in a version comparison.
- Output format stability: whether to add `--json` in v1 or defer.

## 11. Acceptance Criteria

- A `search` command is available and documented.
- Default mode returns versions where matched path is present.
- `--changed-only` returns only versions where matched path state changed.
- Ordering is newest version first.
- Substring matching works in default mode.
- Glob matching works with `--glob`.
- Prefix filtering works with `--path-prefix`.
- `--ignore-case` affects query/glob/prefix behavior consistently.
- Invalid input produces clear user-facing errors with non-zero exit.

## 12. Validation and Test Plan

Implementation validation should follow repository conventions (`make` targets):

- **Unit tests** (`make unit`):
  - parser/flag handling for `search`.
  - controller behavior for presence vs changed-only modes.
  - matching helper behavior (substring/glob/prefix, case-sensitive vs ignore-case).
- **Integration tests** (`make integration`):
  - end-to-end CLI output ordering newest-first.
  - presence mode results across multiple versions.
  - changed-only behavior on add/modify/remove scenarios.
  - prefix scoping and glob behavior against realistic paths.
- **Full gate** (`make lint` and `make test`):
  - formatting/lint/import-layer constraints remain green.
  - full suite passes before merge.

## 13. Risks and Mitigations

- **Risk:** Large manifests may make broad presence queries slow.
  - **Mitigation:** Start with indexed path columns where available and constrain via prefix early; profile representative trees.
- **Risk:** Case-insensitive matching behavior differs across environments.
  - **Mitigation:** Centralize normalization/matching logic and cover with cross-case tests.
- **Risk:** Changed-only semantics are ambiguous (especially adds/removes).
  - **Mitigation:** Lock semantics in tests and docs before merge.
- **Risk:** Layering violations while adding data access paths.
  - **Mitigation:** Keep orchestration in controllers, DB logic in components, contract via ports, and rely on existing import-linter checks.

## 14. Milestones / PR Plan

1. **PR 1 - CLI surface + command DTO**
   - Add parser options and command model.
   - Add placeholder runner/controller wiring.
2. **PR 2 - Presence mode implementation**
   - Implement substring + glob + prefix filters.
   - Ensure newest-first ordering and integration coverage.
3. **PR 3 - Changed-only mode**
   - Implement diffing semantics across versions.
   - Add add/modify/remove scenario tests.
4. **PR 4 - Hardening and docs**
   - Performance tuning where needed.
   - Finalize operator docs and examples.

## 15. Phased Implementation Plan

### Phase 0 - Decision lock (before coding)

#### Goal
Remove ambiguity so implementation is straightforward.

#### Scope
- Confirm final CLI shape:
  - `backuper search <backup_root> <query> [--glob] [--path-prefix <prefix>] [--ignore-case] [--changed-only] [--limit N] [--json]`
- Lock behavior:
  - default mode = presence
  - ordering = newest first (`created_at DESC`, tie-break `version DESC`)
  - `--ignore-case` applies to query, glob, and prefix
  - changed-only includes first-seen and reappear-after-missing
- Lock output contract (human-readable and JSON shape).

#### Exit criteria
- No open behavior questions remain.

### Phase 1 - CLI skeleton and contract

#### Goal
Add command plumbing and tests, without heavy logic.

#### Scope
- Add `SearchCommand` DTO.
- Add parser flags and validation.
- Wire dispatch and runner entrypoint (`run_search` stub).
- Add unit tests for parse/dispatch matrix.

#### Validation
- `make unit`
- `make lint`

#### Exit criteria
- `search` command is parseable and correctly routed.

### Phase 2 - Presence mode MVP

#### Goal
Ship usable search with filtering and ordering.

#### Scope
- Extend `BackupDatabase` port with presence-search API.
- Implement SQLite query behavior:
  - substring matching by default
  - glob matching via `--glob`
  - optional prefix filter via `--path-prefix`
  - case-insensitive matching via `--ignore-case`
  - newest-first ordering
- Add `controllers/search.py` orchestration and runner output.

#### Validation
- `make unit`
- `make integration`
- `make lint`

#### Exit criteria
- Presence-mode `search` works end-to-end.

### Phase 3 - Changed-only mode

#### Goal
Add historical transition semantics without regressing MVP.

#### Scope
- Implement `--changed-only` transition detection:
  - add
  - modify
  - remove
  - reappear
- Preserve newest-first output ordering.
- Add unit and integration coverage for transitions and edge cases.

#### Validation
- `make unit`
- `make integration`
- `make lint`

#### Exit criteria
- Changed-only behavior matches agreed semantics and tests.

### Phase 4 - Hardening and docs

#### Goal
Make the feature stable and operator-friendly.

#### Scope
- Finalize docs and examples.
- Add edge-case coverage:
  - empty/no-match cases
  - special characters
  - large result handling (`--limit`)
- Optional performance pass for broad queries.

#### Validation
- `make lint`
- `make test`

#### Exit criteria
- Full test suite and lint pass; docs reflect final behavior.
