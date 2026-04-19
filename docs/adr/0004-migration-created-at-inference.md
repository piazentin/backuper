# ADR-0004: `created_at` inference when migrating CSV → SQLite

## Date

2026-04-19

## Status

Accepted

## Context

SQLite stores **`created_at`** per version ([ADR-0003](0003-version-ordering-and-most-recent.md)). When importing existing per-version CSV files, that timestamp must be **inferred** — there is no column in CSV for it.

## Decision

1. **Parsable default filenames**  
   The runtime’s default version filenames follow:

   **`YYYY-MM-DDTHHMMSS.csv`**  

   Example: **`2026-02-01T094441.csv`** → version name (stem) **`2026-02-01T094441`**.

   - **Date:** `YYYY-MM-DD` (Gregorian calendar).  
   - **Separator:** literal **`T`**.  
   - **Time:** **`HHMMSS`** — six digits, 24-hour wall time without colons (hours, minutes, seconds).

   This matches the CLI default version string from [`argparser.py`](../../src/backuper/entrypoints/cli/argparser.py): `datetime.now().strftime("%Y-%m-%dT%H%M%S")` (local timezone context for `now()`).

   When the version name matches this pattern, **`created_at`** is derived by **parsing** the stem into an absolute time, then **normalizing to UTC** for storage at **millisecond** precision (same precision rules as mtime fallback).

2. **Fallback: file mtime**  
   If the version name is **not** parsable under the rule above, set **`created_at`** from the **CSV file’s last modification time** (`mtime`).

3. **Storage precision**  
   Persist **`created_at`** with **millisecond** precision (or finer if the DB supports it; callers compare at ms resolution). Prefer **UTC** consistently for stored values.

4. **Collisions**  
   If two versions normalize to the **same** **`created_at`** (including migration edge cases), break ties by **lexicographic order on version name** (same tie-break as [ADR-0003](0003-version-ordering-and-most-recent.md)).

5. **Dotfiles**  
   Ignore **dot-prefixed** filenames when scanning version CSVs (e.g. macOS AppleDouble **`._name.csv`** sidecars). They are **not** versions and must not be migrated as such — consistent with existing CSV listing behaviour.

## Consequences

- Migration tooling must implement the **same** parse and fallback rules as the SQLite schema expects for **`created_at`**.
- Custom version names that do not match the default pattern rely on **mtime**, which may not reflect the original backup intent; operators should be aware in release notes.

## Related

- [docs/csv-migration-contract.md](../csv-migration-contract.md)
- [ADR-0003: Version ordering and most recent](0003-version-ordering-and-most-recent.md)
