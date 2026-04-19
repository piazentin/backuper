# ADR-0002: Version lifecycle, transactions, and default visibility

## Date

2026-04-19

## Status

Accepted

## Context

CSV manifests append rows incrementally; crash mid-run yields a partial version with no explicit machine-readable “in progress” state. SQLite allows explicit version metadata and clearer recovery semantics. Controllers write blobs to the file store **before** manifest rows (`filestore.put` then `add_file`), so orphan blobs under `data/` remain possible regardless of manifest transaction size.

## Decision

1. **Version states**  
   Each version row supports at least **`pending`** (backup started, not finished) and **`completed`** (backup finished successfully). Exact column names are implementation detail; semantics are fixed here.

2. **Lifecycle**  
   - At **start** of a `new` / `update` run: insert the version (or transition it) to **`pending`**.  
   - At **successful end**: transition to **`completed`**.  
   - Commit strategy: **one transaction per file row** (each `add_file` durable independently), aligned with historical CSV behaviour, unless a future ADR narrows this for performance.

3. **Default visibility**  
   **`pending` versions are not visible** through the default **`BackupDatabase`** surface: they do not appear in **`list_versions`**, are not returned by **`most_recent_version`**, and are not targets for normal **`restore`** / **`verify-integrity`** enumeration. Optional extended APIs or flags (e.g. for tooling or recovery) may expose `pending` later; they are out of scope for default CLI behaviour.

4. **Directory entries**  
   Directory rows remain **pure markers** for empty directories on restore (same conceptual model as CSV `d` rows). No additional semantics beyond that in the manifest schema.

## Consequences

- Mid-run, default consumers see **no new completed version** until the final transition to **`completed`** — consistent with “not visible by default.”
- Operators may need explicit tooling to **inspect or clean up** abandoned `pending` rows after crashes (future ops docs).
- Orphan blobs after `put` without a matching committed row remain a **separate** concern from manifest transaction boundaries; this ADR does not introduce blob GC.

## Related

- [ADR-0001: SQLite manifest store](0001-sqlite-manifest-store.md)
- [ADR-0003: Version ordering and most recent](0003-version-ordering-and-most-recent.md)
