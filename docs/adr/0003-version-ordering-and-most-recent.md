# ADR-0003: `list_versions` ordering and `most_recent_version`

## Date

2026-04-19

## Status

Accepted

## Context

The **`BackupDatabase`** port will expose **`most_recent_version`** (new) alongside existing methods. CSV-backed trees today infer “most recent” by **lexicographic maximum of version name** (`CsvDb.get_most_recent_version`). SQLite can persist a **`created_at`** timestamp per version for a more intuitive ordering. CSV is expected to be **deprecated in the short term**; dual semantics are acceptable only during transition.

## Decision

1. **`list_versions`**  
   Return version names in **ascending lexicographic order** (Unicode string sort of the version identifier) as a **port-level contract across backends**. Callers that previously sorted results for stability should get deterministic ordering from the port.  
   This is a **behavioural change** for any adapter that currently returns filesystem iteration order rather than a sorted result. In particular, the legacy CSV implementation must **sort version names before returning them**; returning raw `os.listdir()` order does **not** satisfy this contract.

2. **`most_recent_version` — SQLite**  
   Define “most recent” as the **`completed`** version with the greatest **`created_at`**.  
   **`created_at`** is stored when the version row is created (implementation aligns with SQLite adapter).  
   **Tie-break:** If two versions share the same **`created_at`**, choose the **lexicographically greater** version **name**.

3. **`most_recent_version` — CSV (legacy)**  
   Until CSV support is removed, infer “most recent” as **lexicographic maximum of version name** among existing version CSV basenames (same rule as today). **`created_at`** is **not** stored in CSV; the port implementation derives ordering from names only.

4. **Deprecation caveat**  
   While both backends exist, **`most_recent_version`** may **differ** between CSV and SQLite for the same logical version strings if SQLite uses time-based ordering. Callers must treat this as a **transition** behaviour. After CSV removal, **only** the SQLite semantics (**`created_at`**, with lexicographic tie-break) apply.

## Consequences

- Tests and docs must distinguish **CSV legacy** vs **SQLite** expectations where **`most_recent_version`** is asserted.
- New backups should use SQLite for predictable time-based “most recent” once wired.

## Related

- [ADR-0002: Version lifecycle](0002-version-lifecycle-and-transactions.md)
- [ADR-0004: Migration `created_at` inference](0004-migration-created-at-inference.md)
- [`AGENTS.md`](../../AGENTS.md) (historical CSV lexicographic note — may need cross-link update when SQLite is default)
