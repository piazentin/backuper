# SQLite manifest — operations guide

This document is the operator reference for the **SQLite backup manifest**: where it lives on disk, how `backuper` opens it, how to back it up safely, how to interpret contention and recovery, and how to query it with `sqlite3`.

---

## Where the manifest lives

- **Path:** `<backup_root>/<db_dir>/<sqlite_filename>` — defaults are `<backup_root>/db/manifest.sqlite3`. Deployments may override `db` and `manifest.sqlite3` via application configuration.
- **One logical database** per backup tree. With **`journal_mode=WAL`**, SQLite may create **companion files** next to the main file while the DB is open or before checkpoint:
  - `manifest.sqlite3-wal`
  - `manifest.sqlite3-shm`  
  Treat safe copies as **`.backup` / `Connection.backup`**, or **checkpoint + coordinated multi-file copy**, or a **filesystem snapshot** — not “copy only the main `.sqlite3` file” without qualification, or you can miss not-yet-checkpointed data.
- **Runtime policy:** runtime CLI commands (`new`, `update`, `verify-integrity`, `restore`) use the **SQLite manifest only**.
- **Legacy CSV trees:** a tree that only has CSV manifests is a **pre-migration** tree, not a runtime-ready tree for current CLI operations.
- **Mixed / partial states:** if SQLite manifest artifacts are missing, incomplete, or unreadable, runtime commands fail fast with guidance; they do not auto-repair by switching to CSV.

---

## Connection defaults (PRAGMA policy)

`backuper` configures each manifest connection when the database is opened:

| Setting | Value | Notes |
|--------|--------|--------|
| `foreign_keys` | `ON` | Referential integrity between `versions` and child tables. |
| `journal_mode` | `WAL` | Companion `-wal` / `-shm` files may exist (see above). |
| `synchronous` | `NORMAL` | Balanced durability with WAL; tunable via env (below). |
| `busy_timeout` | `5000` ms | Database-layer wait before surfacing `SQLITE_BUSY` under contention. |

**No extra tuning in product** for `wal_autocheckpoint`, `mmap_size`, or `auto_vacuum` — SQLite defaults apply for those settings.

**Edge case:** unusual network filesystems or exotic `/tmp` layouts for SQLite temp files are **unsupported** edge cases; prefer local, well-behaved storage for the active manifest.

---

## Environment variables (manifest SQLite)

| Variable | Purpose | When unset |
|----------|---------|------------|
| `BACKUPER_SQLITE_SYNCHRONOUS` | Override `PRAGMA synchronous` | Code uses **`NORMAL`**. Accepts symbolic `OFF`, `NORMAL`, `FULL`, `EXTRA` (case-insensitive) or numeric `0`–`3`. Invalid values fail at connection time with a clear error. |

### Env vs code defaults

| Behavior | Env-tunable? | Default |
|----------|----------------|---------|
| `synchronous` | **Yes** — `BACKUPER_SQLITE_SYNCHRONOUS` | `NORMAL` |
| `busy_timeout` (5000 ms) | No (code only) | `5000` |
| `foreign_keys`, `journal_mode=WAL` | No | `ON`, `WAL` |

Only **`synchronous`** is exposed via environment variable among manifest PRAGMAs; everything else follows code defaults and this document.

---

## SQLite version for examples

SQL examples below assume the **SQLite library embedded in CPython** for the same Python versions the package supports (currently **3.11+**).

**Verify your runtime:**

```bash
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

That is the engine `backuper` uses. If you also use the standalone `sqlite3` CLI, check `sqlite3 --version`; it may differ from the embedded library.

**Example:** On a typical CPython **3.11** install, this reports **3.53.0** (your build may vary). Use features compatible with your embedded version when adapting queries.

---

## Contention, parallelism, and single-writer expectations

### Supported model

- **One writer** at a time: a single active `backuper` process performing backup/write work against a given manifest database.
- **Multiple readers** are compatible in principle under **WAL** (e.g. read-only `sqlite3` or reporting tools).

### Concurrent `backuper` processes

Running two **writers** (e.g. two `new`/`update` runs) against the **same** backup tree is **not** a supported configuration. Expect lock contention: SQLite may return **`SQLITE_BUSY`** after the configured **`busy_timeout`** (5000 ms) elapses.

### External tools while `backuper` runs

- **Read-only** opens are **allowed**. Under load, readers may still see occasional **`SQLITE_BUSY`** when contending with the writer.
- **Discourage** tools that open the database for **write** or hold **long** read transactions.

WAL gives readers a **snapshot** of the database as of a consistent point; writers do not block readers indefinitely in the usual WAL pattern, but contention can still occur.

### `SQLITE_BUSY` and retries

Rely on SQLite’s **`busy_timeout`** at the database layer. The product does not add a separate app-level retry policy; if errors persist after waits, treat it as sustained contention or another writer.

### Incomplete / unreadable manifest on read

- After an **abrupt stop**, a **`pending`** version may exist. Default **`BackupDatabase`** / CLI behavior **does not list** `pending` versions in normal listing or “most recent” — you see **no new completed version** until a run **finishes** and transitions to **`completed`**. **Re-run backup** is the normal recovery path.
- **Corrupt / missing database**, integrity, and restore: see **Integrity and recovery** and **Backup, copy, replication, and archival** below.

---

## Backup, copy, replication, and archival

### Blessed backup

Prefer **`sqlite3` `.backup`** or **`Connection.backup`** to a **single** destination file (no separate WAL/SHM beside that copy). Do **not** treat “checkpoint then copy **only** the main file” as a safe primary procedure — WAL can hold commits not yet folded into the main file.

**Fallback:** **Quiesce** the writer, then copy **main + `-wal` + `-shm`** together, or copy from a **consistent filesystem snapshot**.

### Tree-level backups

Backing up the whole tree including `db/` is **OK** when the manifest writer is **quiesced** **or** the tree is captured by a **consistent snapshot** at one instant. A **live** copy of `db/` while `backuper` writes risks an **inconsistent** set of files or a **stale** WAL relative to the main file — use the blessed backup approach above or a snapshot.

### Live sync

**Discourage** treating the **active** manifest directory as a safe replication target **while** `backuper` is writing (cloud sync, NFS, SMB). Prefer: sync **after** a run completes, sync a **`.backup`** artifact, or sync from a **snapshot**.

### Multi-file copy races

Copying `*.sqlite3` + `-wal` + `-shm` by hand is **race-prone** unless the DB is **idle** or the copy is from a **consistent snapshot**. Prefer **`.backup` / `Connection.backup`**.

### Filesystem snapshots

Snapshots (e.g. ZFS, LVM) capture **all** DB-related files at **one** time and are often adequate for disaster recovery. For **portable** off-site archives, still prefer a single-file `.backup` / `Connection.backup` output.

### `VACUUM` and checkpoint

- Optional **`PRAGMA wal_checkpoint(TRUNCATE)`** or **`FULL`** before **off-site** or **size-sensitive** copies — **documentation only**; not automated product behavior.
- **`VACUUM`**: optional and **rare** (e.g. if you **measure** bloat); no scheduled default.

---

## Integrity and recovery

### `quick_check` vs `integrity_check`

| Check | Weight | When to use |
|-------|--------|-------------|
| `PRAGMA quick_check` | Lighter | Default **on-demand** sanity check. |
| `PRAGMA integrity_check` | Full | After **`quick_check`** fails, returns non-`ok`, or strong suspicion of corruption (`SQLITE_CORRUPT`, storage mishaps). Can be **slow** and emit **many** lines. |

**When to run (not exhaustive):** after **restoring** a manifest from a file backup; when **troubleshooting** manifest errors; optional occasional hygiene — **not** every backup run.

Prefer checking a **`.backup`** copy or a **quiesced** DB to avoid writer contention.

**Reading results:** one line `ok` vs one or more **error** lines (full check may be verbose).

This guide does **not** include a deep **`SQLITE_CORRUPT` recovery playbook**; rely on **manifest file backup and restore** (see **Backup, copy, replication, and archival** above).

### Pending version after crash

A version row can be **`pending`** (backup started, not finished) or **`completed`**. After a crash, **`pending`** may remain. Normal listing does not show `pending` versions; **re-run backup** is the usual fix. Optional read-only SQL can inspect `pending` rows. Manual **`DELETE`** or cleanup can leave **orphan blobs** under `data/` (blobs written before manifest rows) — the product does not garbage-collect those automatically.

### `user_version` / schema mismatch

Schema evolution uses **`PRAGMA user_version`** with **forward-only** migrations. On open, an **unsupported** schema version fails fast with a clear message. If the database is **too new** for your `backuper` binary — **upgrade `backuper`**. If the binary is **newer** than the database schema — use the supported upgrade path or **restore** a backup that matches the tool version.

---

## Manifest schema (v1)

Tables (simplified; the database includes indexes for lookups and ordering not listed here):

- **`versions`:** `name` (PK), `state` (`pending` / `completed`), `created_at` (real).
- **`version_files`:** `id`, `version_name` (FK → `versions`), `restore_path`, `hash_algorithm`, `hash_digest`, `storage_location`, `compression`, `size`, `mtime`.
- **`version_directories`:** `id`, `version_name` (FK), `restore_path` — markers for empty directories on restore.

Behavioral summary: new versions start **`pending`**; successful completion transitions to **`completed`**. File rows are committed in **small transactions** (commit-per-row style). **`list_versions`** / normal CLI enumeration use **completed** versions only unless you query SQL directly.

---

## Export, query, and audits

### SQL and `sqlite3` recipes

Use **`sqlite3` + SQL** against the schema above, **read-only** when probing a live tree (see **External tools while `backuper` runs**). There are **no** dedicated `backuper` CLI subcommands for canned manifest export or query.

### Example queries

Open read-only when probing a live tree (URI mode is typical):

```bash
sqlite3 "file:/path/to/backup/db/manifest.sqlite3?mode=ro" \
  "PRAGMA query_only=ON; SELECT sqlite_version();"
```

**Completed versions (names, ordered):**

```sql
SELECT name, state, created_at
FROM versions
WHERE state = 'completed'
ORDER BY created_at, name;
```

**File count per completed version:**

```sql
SELECT v.name, COUNT(f.id) AS file_count
FROM versions v
LEFT JOIN version_files f ON f.version_name = v.name
WHERE v.state = 'completed'
GROUP BY v.name
ORDER BY v.name;
```

**Inspect hashes (algorithm + digest):**

```sql
SELECT version_name, restore_path, hash_algorithm, hash_digest
FROM version_files
WHERE version_name = 'YOUR_VERSION'
ORDER BY restore_path;
```

**Diff file paths between two versions (example — adjust names):**

```sql
SELECT restore_path FROM version_files WHERE version_name = 'v1'
EXCEPT
SELECT restore_path FROM version_files WHERE version_name = 'v2';
```

**Optional — `pending` rows (inspection only):**

```sql
SELECT name, state, created_at FROM versions WHERE state = 'pending';
```

### Sensitive paths

Query output can expose **paths** and metadata. Control **access** and **handling** of results; use **hash-only** or column-limited queries for audits when appropriate. The product does not redact query output automatically.

### Stable machine-readable exports

There is **no** commitment that `backuper` will ship stable CSV/JSON manifest dumps, and no guarantee that ad hoc **`sqlite3`** `.mode` / scripted exports are a **stability**-grade contract for automation.

---

## Observability and diagnostics

### Logging

Prefer a **minimal** SQLite-related logging surface — avoid noise; no broad taxonomy of logs for expected conditions.

### CLI exit codes and messages

The CLI entrypoint `main()` in [`src/backuper/entrypoints/cli/main.py`](../src/backuper/entrypoints/cli/main.py) wraps parsing and dispatch in a small error boundary — this section describes observable behavior, not a separate stability contract for automation.

| Outcome | Exit code | Notes |
|---------|-----------|--------|
| Success | `0` | Normal completion after dispatch. |
| User-facing errors | `1` | **`UserFacingError`** and subclasses (including **`CliUsageError`**) — full message on **stderr**, no traceback. Covers invalid usage reported by the app, backend resolution / manifest bootstrap failures, and domain errors (e.g. missing paths, version not found). |
| Unexpected errors | `1` | Logged at **ERROR** with traceback; **stderr** shows a short generic line (current text: “An unexpected error occurred.”). |
| **`argparse`** | `SystemExit` | **`main()`** re-raises **`SystemExit`** unchanged (not mapped to `1`). Standard **Python 3 `argparse`**: **`--help` / `-h`** exits **`0`**; unknown flags, missing required arguments, and similar usage problems typically exit **`2`**. |

SQLite-related resolver and bootstrap messages from wiring are prefixed with **`SQLite manifest:`** so operators can tell them apart from other usage lines in **stderr**.

There is **no** separate exit-code taxonomy for SQLite-only failure modes beyond **`1`** vs success **`0`** vs **`argparse`**’s **`SystemExit`** codes above.

### Preflight integrity in product

**No** automatic `quick_check` / `integrity_check` before commands. Operators who need verification run `PRAGMA quick_check` / `PRAGMA integrity_check` as described in **Integrity and recovery** above. Treating a **corrupt** manifest as an advanced operator scenario — not the default end-user path.

The CLI does not add verbose SQLite “health hints” beyond normal logging.

---

## Environment and filesystem

- **Local vs network:** Normal case is **local** (or well-behaved POSIX) storage. Network paths (NFS, SMB, cloud mounts) are **best-effort** — expect **latency**, **locking**, and **coherency** risk; **not** recommended for the **active** manifest while `backuper` writes. See **Live sync** and **Contention, parallelism, and single-writer expectations** above.

- **Paths in shell:** When passing paths on the command line, **quote** and **escape** safely; prefer **SQLite URI** forms or `.open` in the `sqlite3` shell for spaces and unusual characters.

- **Writable manifest:** The manifest database path must be **writable** for normal operation. **Read-only** mounts or read-only containers **prevent** correct behavior.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|----------------|--------|
| `SQLITE_BUSY` / timeouts | Another writer or heavy contention | Ensure **one writer**; see **Concurrent `backuper` processes** above; retry after a quiet window. |
| Errors opening DB / “read-only” failures | Read-only mount or permissions | Fix mount/permissions (see **Writable manifest** above). |
| No new completed version after crash | `pending` version only | **Re-run** backup; optional SQL to inspect `pending` (see **Pending version after crash**). |
| Schema / `user_version` errors | Binary vs DB mismatch | Upgrade or restore a matching backup. |
| Suspect file after copy/restore | Incomplete multi-file copy | Use **Blessed backup**; run **`quick_check`** / **`integrity_check`** (see **Integrity and recovery**). |

For corrupt databases, use **backup/restore** and the integrity checks in this document; there is **no** dedicated **`SQLITE_CORRUPT`** playbook here.

---

## Legacy CSV manifests

Legacy CSV manifests are migration inputs, not an active runtime backend. If your backup tree still has CSV-only manifests, run the migration scripts before using runtime CLI operations:

1. Normalize legacy rows (if needed): `uv run python -m scripts.migrate_version_csv`.
2. Build SQLite manifest from canonical CSV: `uv run python -m scripts.migrate_manifest_csv_to_sqlite`.
3. Validate with `verify-integrity` and a restore smoke test.

For the full end-to-end procedure (including archive/rollback guidance and checks), see [`docs/csv-to-sqlite-migration.md`](csv-to-sqlite-migration.md).
