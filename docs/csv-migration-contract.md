# CSV migration contract

## Operator requirement (read this first)

The **`backuper` runtime** (`new`, `update`, `check`, `restore`) reads **canonical** version CSV rows only—see [Canonical CSV row contract](#canonical-csv-row-contract) and `CsvDb` in `src/backuper/components/csv_db.py`. It does **not** accept legacy short file rows (3 or 5 columns).

If you have an **existing backup tree** whose version manifests still use legacy shapes, you **must** run the standalone migration **before** relying on this version of the tool against that tree:

```bash
uv run python -m scripts.migrate_version_csv --help
```

Migration details, legacy source shapes, dry-run/apply semantics, and rollback artifacts are defined below.

## Scope

- Applies to migration of existing `<backup_root>/<backup_db_dir>/<version>.csv` files.
- Defines the canonical output shape that the runtime expects after migration.

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

The **migration script** accepts legacy file rows with 3, 5, or 7+ columns and converts them to canonical 7-column form. The **runtime** does not; use the script to upgrade old manifests.

### Size and mtime enrichment from the backed-up blob

When `size` and/or `mtime` are **not available** from the CSV row (missing, empty, or legacy rows that never carried them), migration **must** try to populate them from the **content-addressed blob on disk** before falling back to `0` / `0.0`.

Blob resolution (aligned with `LocalFileStore` in `filestore.py`):

- Absolute blob path: `<backup_root>/<backup_data_dir>/<stored_location>`
- Default directory names match runtime config: `backup_data_dir = "data"` unless overridden for the migration run.
- Use the row’s `stored_location` after canonicalization; for 3-column legacy rows, compute `stored_location` with `hash_to_stored_location(sha1hash, is_compressed)` first.
- If both compressed and uncompressed blobs could exist for the same hash, prefer the path that exists on disk; if both exist, prefer the row’s `is_compressed` when known, otherwise document/define a deterministic rule (e.g. prefer uncompressed) and log a warning.

**`size` (logical content size):**

- **Uncompressed blob** (`is_compressed` is false): use `os.path.getsize(blob_path)` — this matches the original file byte length.
- **Compressed blob** (`.zip` with inner name `part001`): use the **uncompressed** size of that zip member (e.g. `ZipInfo.file_size` for `part001`), not the `.zip` file’s size on disk — this matches what a full read would yield and aligns with metadata semantics elsewhere.

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
- Normalize path to the runtime normalizer contract.
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

- Do not run while `new`, `update`, `check`, or `restore` is active.
- Take a filesystem-level backup/snapshot of the backup root first.
- Run dry-run first, review planned changes and any failures.
- Run apply once dry-run output is clean.
- Validate with normal project flows after migration (`make test` for repo validation, and a real `check`/`restore` on migrated data as needed).

Concurrency locks are out of scope for Phase 4.1; this is a documented operational policy.
