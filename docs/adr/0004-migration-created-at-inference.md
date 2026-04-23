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

   When the version name matches this pattern, **`created_at`** is derived by **parsing** the stem into calendar and wall-clock components, then interpreting them as **local civil time in the migration host’s default timezone** (the same zone `datetime.now()` would use on that host at migration time). That **timezone-aware** instant is **normalized to UTC** and stored as **Unix epoch seconds** in SQLite’s **`REAL`** column, **quantized to millisecond resolution** (`round(seconds * 1000) / 1000`), matching `SqliteBackupDatabase.create_version` / `time.time()` (same quantization rules as mtime fallback).

   **Trade-off:** The stem does not record which timezone produced the original backup filename. **`created_at`** from parsing is therefore **stable for a given migration run** but may **differ** if the same tree is migrated on another machine with a different default offset (or different historical DST rules) for the same stem. **`mtime`** fallback is similarly host-dependent. Operators needing predictable cross-host migration should run migration in a controlled environment or rely on **`mtime`** when stems are ambiguous.

2. **Fallback: file mtime**  
   If the version name is **not** parsable under the rule above, set **`created_at`** from the **CSV file’s last modification time** (`mtime`).

3. **Storage precision**  
   Persist **`created_at`** as **UTC epoch seconds** in the **`REAL`** column, at **millisecond quantization**, identical to the live SQLite adapter. Prefer **UTC** consistently for inferred instants.

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
