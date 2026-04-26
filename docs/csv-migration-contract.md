# CSV migration contract

## Operator requirement (read this first)

This document defines the contract for the standalone `scripts.migrate_version_csv` migration workflow. It is a **script-level** contract, not a runtime backend contract.

If you have an **existing backup tree** whose version manifests still use legacy shapes, run this migration first as part of the CSV-to-SQLite runbook:

```bash
uv run python -m scripts.migrate_version_csv --help
```

Run migration with the **project virtual environment** (for example `uv run …` after `uv sync`) so the `backuper` package is importable. Script imports are intentionally limited to shared surfaces (`backuper.models`, `backuper.utils`, `backuper.config`, and selected SQLite adapter wiring) and must not depend on runtime orchestration layers.

The migration currently uses `backuper.utils.zip_payload` for compressed-blob member resolution, keeping the same rules as restore (`LocalFileStore.read_blob`).

Migration details, legacy source shapes, dry-run/apply semantics, and rollback artifacts are defined below.

## Scope

- Applies to migration of existing `<backup_root>/<backup_db_dir>/<version>.csv` files.
- Defines the canonical output shape consumed by downstream migration tooling (not by runtime CLI operations).

## Canonical CSV row contract

Rows are comma-delimited and quoted (`"`), parsed by Python `csv.reader` with UTF-8 input.

### Directory row (canonical)

Expected kind: `d`

Columns:

1. `kind` - literal `d`
2. `normalized_path` - restore-relative directory path (normalized to forward slashes)
3. `reserved` - currently empty string (`""`)

Example:

`"d","photos/2024",""`

### File row (canonical)

Expected kind: `f`

Columns:

1. `kind` - literal `f`
2. `restore_path` - restore-relative file path
3. `sha1hash` - SHA-1 digest string
4. `stored_location` - content-addressed blob location (e.g. `ab/cd/<hash>.zip` style path)
5. `is_compressed` - `True` or `False` (exact string, case-sensitive)
6. `size` - integer bytes (base-10)
7. `mtime` - floating-point Unix timestamp seconds

Example:

`"f","docs/readme.txt","<sha1>","aa/bb/<sha1>.zip","False","1234","1712500000.0"`

## Legacy-to-canonical mapping rules

The **migration script** accepts legacy file rows with 3, 5, or 7+ columns and converts them to canonical 7-column form for downstream migration tooling. Use this script to upgrade old manifests before CSV-to-SQLite migration.

### Size and mtime enrichment from the backed-up blob

When `size` and/or `mtime` are **not available** from the CSV row (missing, empty, or legacy rows that never carried them), migration **must** try to populate them from the **content-addressed blob on disk** before falling back to `0` / `0.0`.

Blob resolution (using the same package helpers referenced by this script):

- Absolute blob path: `<backup_root>/<backup_data_dir>/<stored_location>`
- Default directory names are `db/` and `data/` unless overridden for the migration run.
- Use the row’s `stored_location` after canonicalization; for 3-column legacy rows, compute `stored_location` with `hash_to_stored_location(sha1hash, is_compressed)` first.
- If both compressed and uncompressed blobs could exist for the same hash, prefer the path that exists on disk; if both exist, prefer the row’s `is_compressed` when known, otherwise document/define a deterministic rule (e.g. prefer uncompressed) and log a warning.

**Compressed `.zip` payload member (canonical and legacy):**

For **logical size** and for **which** inner file migration treats as the payload, use this contract's resolution rules:

- Consider **file members only** (non-directory `ZipInfo` entries); stray directory entries do not count toward “how many members” or name matching.
- **Canonical:** if any file member’s **basename** is `part001`, that member is the payload. If more than one such file member exists, the archive is invalid for resolution (migration logs a warning and cannot enrich `size`).
- **Legacy:** if there is **no** `part001` file member, the payload is the **unique** file member whose basename equals the row’s `sha1hash` in **lowercase hex** (same normalization as manifest storage). If there are zero or multiple hash-named file members (and no `part001`), the archive is ambiguous or invalid for resolution.
- **Both layouts:** if both a `part001` file member and a hash-named file member exist, **`part001` wins** (canonical takes precedence).

**`size` (logical content size):**

- **Uncompressed blob** (`is_compressed` is false): use `os.path.getsize(blob_path)` — this matches the original file byte length.
- **Compressed blob** (`.zip`): use the **uncompressed** size of the **resolved** payload member (`ZipInfo.file_size` for that member’s name), not the `.zip` file’s size on disk.

**`mtime`:**

- Use `os.path.getmtime(blob_path)` on the blob file when the CSV does not supply mtime.
- **Limitation:** this is typically **backup write time**, not the original source file’s modification time. Documented as best-effort metadata for migration; acceptable because the alternative is leaving `0.0`.

**Failure / fallback:**

- If the blob path does not exist, is unreadable, or enrichment fails, use `size = 0` and `mtime = 0.0` and **record a warning** (version file, row number, reason). Migration still succeeds unless the error policy below applies.

**When CSV already supplies values:**

- If `size` and `mtime` parse successfully from the row, **keep them** (do not overwrite with blob-derived values). Optional: `--verify-blob` mode could compare CSV vs blob and warn on mismatch; out of scope unless implemented.

### Source: 7+ columns (already canonical-compatible)

- Read only the first 7 columns.
- Ignore columns 8+.
- Re-emit exactly 7 columns in canonical order.
- Parse/coerce:
  - `is_compressed`: `True` -> `True`, all other values -> `False`
  - `size`: empty -> apply [Size and mtime enrichment from the backed-up blob](#size-and-mtime-enrichment-from-the-backed-up-blob), then if still missing -> `0`
  - `mtime`: empty -> apply enrichment, then if still missing -> `0.0`
- Non-empty fields that fail `int` / `float` parse are errors (fail-fast).

### Source: 5 columns

Input: `kind, restore_path, sha1hash, stored_location, is_compressed`

Canonical mapping:

- After boolean coercion for `is_compressed`, set provisional `size` / `mtime` to missing, then apply [blob enrichment](#size-and-mtime-enrichment-from-the-backed-up-blob), then default remainder to `0` / `0.0`.

### Source: 3 columns

Input: `kind, restore_path, sha1hash`

Canonical mapping:

- `stored_location` -> computed from `hash_to_stored_location(sha1hash, False)` (and set `is_compressed` -> `False` for this legacy shape)
- Provisional `size` / `mtime` missing -> apply [blob enrichment](#size-and-mtime-enrichment-from-the-backed-up-blob) (try both compressed and uncompressed blob paths per the resolution rule if needed), then default to `0` / `0.0`

### Directory rows

- Keep `kind=d` rows.
- Normalize path using the migration script's canonical path normalization.
- Emit canonical 3-column shape (`d`, `path`, empty reserved field).

## Error policy

Migration is fail-fast per input file:

- Reject and report with non-zero exit if:
  - row is empty
  - row kind is not `d` or `f`
  - file row has unsupported column count (not 3, 5, or >=7)
  - `size` or `mtime` is **present but not parseable** as `int` / `float` (empty means “try blob enrichment”, not a parse error)
- Missing blob or failed enrichment emits a **warning** and leaves `0` / `0.0`; it does not fail the run unless you add an optional strict mode later.
- Error report must include:
  - version file path
  - row number
  - short reason
- On failure, do not replace the original CSV file.

## Idempotency behavior

Migration must be idempotent:

- Running against an already canonical file yields byte-stable output (or no-op replace).
- Re-running migration on already migrated files must succeed without semantic changes.
- `--dry-run` reports whether a file would change but writes nothing.

Recommended change-detection rule:

- Serialize migrated rows deterministically.
- Compare against current file bytes.
- If unchanged, report `unchanged` and skip replacement.

## Atomic write and rollback artifacts

Apply mode must use atomic replacement and **retain** pre-migration copies:

1. If the version CSV will change, preserve the current file by **copying** it to `<name>.csv.bak` in the same directory (same basename as the CSV, e.g. `v1.csv` → `v1.csv.bak`). Use `copy`, not `rename`, so the original path still exists for the next step until replaced.
2. Write migrated content to a temp file in the same directory.
3. Flush and fsync the temp file.
4. Atomically rename the temp file over the live CSV (e.g. `v1.csv`).

**Do not delete** `<name>.csv.bak` after a successful run. Operators keep these files for rollback and audit; the migration tool must not remove them.

If `<name>.csv.bak` already exists (e.g. re-run or prior migration), do not overwrite it silently: write the new pre-migration copy to a new name (for example `<name>.csv.bak.<timestamp>` or `<name>.csv.bak.1`, `<name>.csv.bak.2`, …) so previous `.bak` files are never deleted by the tool.

If interrupted before the final rename, the original CSV is unchanged; any new `.bak` copy still reflects the pre-interruption state when step 1 completed.

## Maintenance-window execution guidance

Migration is an operator-only maintenance action and should run only during a quiet window:

- Do not run while `new`, `update`, `verify-integrity`, or `restore` is active.
- Take a filesystem-level backup/snapshot of the backup root first.
- Run dry-run first, review planned changes and any failures.
- Run apply once dry-run output is clean.
- Validate migration outcomes with script dry-run/apply reports and follow the CSV-to-SQLite runbook for runtime validation after backend migration.

Concurrency locks are currently out of scope; this remains a documented operational policy.

## Next step: migrate canonical CSV to SQLite

After manifests are canonical, operators can migrate the backup tree to the SQLite manifest backend with `scripts.migrate_manifest_csv_to_sqlite`. Use the end-to-end runbook: [`docs/csv-to-sqlite-migration.md`](csv-to-sqlite-migration.md).
