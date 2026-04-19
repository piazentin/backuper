# SQLite support — Phase 5 discovery (temporary)

| | |
|--|--|
| **Created** | 2026-04-19 |
| **Status** | Scratch / iteration — not normative; replace or fold into ADR/ops docs when Phase 5 is executed |

**Scope:** This file is **only** for **Phase 5 — Operations, observability, and durability hardening** per [`sqlite-support-assessment.md`](sqlite-support-assessment.md). Other phases (migration, CSV posture, resolver UX beyond ops) are out of scope here.

This note captures **research so far** and **open questions** within that Phase 5 boundary. It is a working document for discussion, not a decision record.

---

## Phase 5 target outcome (from assessment)

- Documented **SQLite pragmas** and **recovery** expectations for the **manifest database**.
- Safe **copy/backup** of that database (WAL implies companion files — see [ADR-0001](../adr/0001-sqlite-manifest-store.md)).
- **Export or query** guidance (CLI and/or documented `sqlite3` recipes) for audits and diffs.
- **Performance** characteristics validated for **realistic manifest sizes** (indexes and commit strategy are defined in [ADR-0005](../adr/0005-sqlite-adapter-contract-and-schema-v1.md)).

**Later planning** in the assessment (same phase family): benchmarks, optional commands (`export-manifest`, etc.), tuning.

**Primary ADR references for Phase 5 work:** [ADR-0001](../adr/0001-sqlite-manifest-store.md) (layout, WAL, durability/copy story), [ADR-0005](../adr/0005-sqlite-adapter-contract-and-schema-v1.md) (schema, PRAGMA bootstrap, commit-per-file). Lifecycle semantics for crash/pending narratives: [ADR-0002](../adr/0002-version-lifecycle-and-transactions.md).

---

## Research captured so far (Phase 5–relevant)

### Current implementation snapshot

- `SqliteDb._configure_connection` sets `PRAGMA foreign_keys=ON` and `PRAGMA journal_mode=WAL` ([`sqlite_db.py`](../../src/backuper/components/sqlite_db.py)).
- **No** `synchronous` (or `busy_timeout`, etc.) set in code yet — SQLite defaults apply until explicitly configured.
- Writes use **small transactions** with explicit `commit()` per `create_version`, each `add_file`, and `complete_version` (commit-per-file for file rows), matching ADR-0005.

### Sudden power loss / crash (healthy storage)

- **WAL + SQLite recovery:** After reboot, the next open runs WAL recovery; committed transactions survive; uncommitted work is dropped as a unit (not torn rows inside a single commit).
- **Mid-backup:** A `pending` version may have **partial** file rows committed if `complete_version` has not committed — consistent with ADR-0002 (pending not listed like completed).
- **Risk layers:** Stricter `synchronous` reduces the window where the OS/storage stack loses acknowledged commits; **OFF** is unsafe for a manifest we care about. **Hardware failure** can corrupt below SQLite — backups and `integrity_check` remain the fallback.
- **Copy hazard (not power loss):** Copying **only** the main DB file while `-wal` exists can **omit** not-yet-checkpointed commits — ADR-0001 already calls for checkpoint / `.backup` / `Connection.backup`, not naive single-file copy.

### `PRAGMA synchronous` tradeoffs

- Stricter (**FULL**, **EXTRA**): stronger durability guarantees, **more fsync cost**; hurts throughput when there are **many commits** (manifest commit-per-file pattern).
- **NORMAL** with **WAL** is a common production balance (faster than FULL for many workloads; still not `OFF`).
- Looser than FULL widens the theoretical “lost last commit on power cut” window on weak or lying storage.

### Product decision (discussion; implementation is Phase 5 delivery)

- **Default:** `synchronous=NORMAL`.
- **Override:** expose in code and document an **environment variable** (e.g. `BACKUPER_SQLITE_SYNCHRONOUS`) for `OFF` / `NORMAL` / `FULL` / `EXTRA` (or numeric aliases).

### Out of scope for Phase 5 (listed only to avoid scope creep)

- [Issue #50](https://github.com/piazentin/backuper/issues/50) (async offloading / thread ownership): separate track unless Phase 5 explicitly expands.

---

## Decisions log (iterative)

Section-by-section agreements; **normative** product/ops text still belongs in final operator docs / code when Phase 5 is implemented.

### Section A — Durability, PRAGMAs, connection defaults — **decided**

| ID | Decision |
|----|----------|
| **A1** | **`synchronous`:** default **`NORMAL`**; env override (e.g. `BACKUPER_SQLITE_SYNCHRONOUS`) with validated values — already agreed; ship + document in Phase 5. |
| **A2** | **`busy_timeout`:** set a **default in code** of **5000 ms** (5 s) so transient contention waits instead of failing immediately; **document** in operator doc; optional env to tune/disable later if needed. |
| **A3** | **`wal_autocheckpoint`:** keep **SQLite default**; **no extra documentation** beyond what’s implied by WAL/copy guidance elsewhere. |
| **A4** | **`mmap_size`:** **SQLite default** (no override). |
| **A5** | **`auto_vacuum`:** **not required** for Phase 5; no dedicated ops section unless real-world growth proves otherwise. |
| **A6** | **`temp_store` / weird `/tmp`:** **no code change**; operator doc **one line** that unusual network FS / temp layouts are unsupported edge cases. |
| **A7** | **Where to record PRAGMA policy:** **operator documentation only** (no new ADR solely for this). |
| **A8** | **SQLite version for CLI recipes:** **pin a minimum** aligned with **embedded SQLite in the oldest supported Python** ([`requires-python`](../../pyproject.toml) is `>=3.11`). Concretely: state that examples target the feature set of that embedded library; **verify** the floor with `import sqlite3; sqlite3.sqlite_version` (and optionally `sqlite3 --version` for the CLI) on Python **3.11** in CI or a one-off check, and record the pinned minimum in the operator doc. |

### Section B — Contention, parallelism, single-writer expectations — **decided**

| ID | Decision |
|----|----------|
| **B1** | **Supported model:** **one writer** to the manifest database at a time (one active `backuper` process doing backup/write work for that DB); **multiple readers** are supported in principle under **WAL** (e.g. read-only `sqlite3` or reporting tools). State this clearly in the operator doc. |
| **B2** | **Concurrent `backuper` against the same tree:** Phase 5 is **documentation only** — describe expected behavior (e.g. unsupported concurrent writers, **`SQLITE_BUSY`** after **`busy_timeout`** per **A2**). **Stronger product behavior** (detection, dedicated errors, locking) is **out of Phase 5** and tracked on **GitHub**; **link that issue** from the operator doc when Phase 5 ships (insert issue URL when known). |
| **B3** | **External tools, read-only, while `backuper` runs:** **Allowed** when the tool opens the DB **read-only**; operators should expect occasional **`SQLITE_BUSY`** under contention. **Discourage** tools that open for write or hold long transactions. Document WAL snapshot semantics briefly. |
| **B4** | **`SQLITE_BUSY`:** Rely on SQLite’s **`busy_timeout`** (**5000 ms**, **A2**) for wait/retry at the database layer; **no additional app-level retry policy** required for Phase 5. Document user-visible guidance (transient wait vs persistent contention / another writer). |
| **B5** | **Incomplete / unreadable manifest on read:** operator doc uses the **crash / “pending”** angle — short pointer to [**ADR-0002**](../adr/0002-version-lifecycle-and-transactions.md): after abrupt stop, a **pending** version may exist; what that implies for listing vs completed versions; re-run backup / expectations. **No** new resolver rules ([**ADR-0006**](../adr/0006-backend-resolution-policy.md) unchanged). **Corrupt / missing DB, integrity, and restore** belong in **section D** (not a second recovery playbook under B). |

### Section C — Backup, copy, replication, archival — **decided**

| ID | Decision |
|----|----------|
| **C1** | **Blessed backup procedure:** **`sqlite3` `.backup`** or **`Connection.backup`** to a **single** destination file (no WAL/SHM alongside the copy) is the **default** operator procedure in Phase 5 docs. **Fallback:** **quiesce** the writer, then copy **main + `-wal` + `-shm`** together, or copy from a **consistent filesystem snapshot** (see **C5**). Do **not** present “checkpoint then copy **only** the main file” as a safe primary path — at most a **warning**, consistent with [**ADR-0001**](../adr/0001-sqlite-manifest-store.md). |
| **C2** | **Tree-level backups** (whole backup root including `db/`): **OK** when the manifest **writer is quiesced** **or** the tree is captured by a **consistent snapshot** at one instant. **Warn:** a **live** copy of `db/` while `backuper` is writing risks an **inconsistent trio** or **stale WAL** relative to the main file; point readers to **C1** / **C4** for safe manifest backup. |
| **C3** | **Live sync** (cloud sync, NFS, SMB) of the backup root: **discourage** treating the **active** manifest directory as a safe replication target **while** `backuper` is writing. Prefer: sync **after** a run completes, sync a **C1** **`.backup`** artifact, or sync from a **snapshot** (**C5**). |
| **C4** | **Multi-file copy race:** **Prefer** **`.backup` / `Connection.backup`** so operators need not hand-copy **`*.sqlite3` + `-wal` + `-shm`**. If copying those files: state they are **race-prone** unless the DB is **idle** (no writer) or the copy is from a **consistent snapshot**; **`.backup`** remains the default recommendation. |
| **C5** | **Filesystem snapshots** (e.g. ZFS, LVM): **short** ops note — snapshots capture **all** DB files at **one** point in time and are **adequate** for many disaster-recovery copies. Still **prefer** **C1** for **portable** off-site archives. |
| **C6** | **`VACUUM` / checkpoint:** Document **optional** **`PRAGMA wal_checkpoint(TRUNCATE)`** or **`FULL`** before **off-site** or **size-sensitive** copies to flush/shrink WAL — **documentation only** in Phase 5 (not automated product behavior). **`VACUUM`:** **optional** / **rare** (e.g. if operators **measure** bloat); **no** default scheduled **`VACUUM`** in Phase 5 ops. [Issue #50](https://github.com/piazentin/backuper/issues/50) remains **out of scope** unless Phase 5 explicitly expands. |

### Section D — Corruption, integrity, and recovery — **partial** (**D2** deferred)

| ID | Decision |
|----|----------|
| **D1** | **`PRAGMA quick_check`** vs **`PRAGMA integrity_check`:** document **both** with **`sqlite3`** examples; **`quick_check`** is the **lighter** default for **on-demand** verification. **`integrity_check`** (full) when **`quick_check`** fails, returns non-**`ok`**, or there is **strong suspicion** of corruption (e.g. after errors, **`SQLITE_CORRUPT`**, or a **bad** copy). **When to run (not exhaustive):** after **restoring** a manifest from a file backup (**C1**); when **troubleshooting** manifest/DB errors or **storage** mishaps; **optional** occasional hygiene — **not** implied as **every** backup run (full **`integrity_check`** can be **slow**). Prefer checking a **C1** `.backup` copy or a **quiesced** DB when practical to avoid **writer** contention (**B3**/**B4**). **Reading results:** single line **`ok`** vs one or more **error** lines (full check may emit **many** lines). |
| **D2** | **Deferred — not delivered in Phase 5 operator doc:** no dedicated **`SQLITE_CORRUPT`** / corruption **recovery playbook** in this phase. Operators rely on **generic manifest file backup and restore** (**C1**–**C4**) until a **future** doc iteration. (Checklist **D2** remains **open**.) |
| **D3** | **Pending version after crash:** align with [**ADR-0002**](../adr/0002-version-lifecycle-and-transactions.md): **`pending`** may exist after abrupt stop; **default** APIs **hide** `pending` — operators see **no new completed version** until a run **completes** successfully. **Re-run backup** is the normal path. Document **optional** read-only **`sqlite3`** queries to **inspect** `pending` rows; any **manual cleanup** (**DELETE**, etc.) carries **orphan blob** caveats under `data/` (**ADR-0002**); **no** blob GC in Phase 5. |
| **D4** | **`PRAGMA user_version` / schema mismatch:** operator doc mirrors [**ADR-0005**](../adr/0005-sqlite-adapter-contract-and-schema-v1.md) — **`user_version`** is **forward-only**; on open, **unsupported** schema → **fail-fast** with a **clear** message. **Too new** (DB ahead of binary): **upgrade `backuper`**. **Too old** (binary ahead of DB): use the **supported upgrade** path or **restore** a matching backup — **no** CSV migration narrative in this subsection. |

### Section E — Export, query, audits, and privacy — **decided**

| ID | Decision |
|----|----------|
| **E1** | **Deliverable shape:** Phase 5 operator documentation delivers **`sqlite3` + SQL recipes** against the manifest schema ([**ADR-0005**](../adr/0005-sqlite-adapter-contract-and-schema-v1.md)), including connection/path guidance and **read-only** posture (**B3**); cross-link **A8** (embedded SQLite floor). **No** new **`backuper` CLI helpers** for manifest export or canned queries in Phase 5. |
| **E2** | **Example queries:** **curated** examples for **completed** versions, **per-version file counts**, **hash-oriented** reports, and **diffs between two versions**; **optional** queries that surface **`pending`** rows for inspection with explicit semantics vs default CLI visibility (**ADR-0002**). |
| **E3** | **Sensitive paths:** short **privacy** warning — query output can expose **sensitive paths** and metadata; operators control **access** and **handling** of results; **no** automated **redaction** in Phase 5; suggest **hash-only** or **column-limited** queries when appropriate for audits. |
| **E4** | **Stable machine-readable output (CSV/JSON):** **not in Phase 5** — no **`backuper` CLI** commitment to stable **CSV/JSON** (or similar) manifest dumps, and **no** Phase 5 operator promise that **`sqlite3`** `.mode` / scripted exports are a **stability**-grade contract; revisit only with a **future** CLI or documentation iteration. |

### Section G — Observability and diagnostics — **decided** (**G4** not in Phase 5)

| ID | Decision |
|----|----------|
| **G1** | **Minimal logging:** Phase 5 favors the **smallest** practical SQLite-related logging surface — **avoid** log noise and **do not** introduce broad “taxonomy” logging or extra chatter for expected conditions. Operator doc may state this principle briefly; **no** mandate to add logs solely for observability. |
| **G2** | **CLI exit codes / messages:** **Document** current behavior and apply **small** clarifications where low-risk so **usage/config** errors are distinguishable from **manifest / SQLite** failures within the Phase 5 touch surface — consistent with the **G2** “document + normalize” posture; **no** requirement for a **new** dedicated exit code for corruption unless it falls out naturally from existing detection. |
| **G3** | **Preflight / automated checks:** **No** optional preflight **`integrity_check`** (or **`quick_check`**) **in product** — **no new CLI** or env-driven automatic check before commands. Operators who need verification use **`PRAGMA quick_check`** per **D1** (sufficient); **full** **`integrity_check`** remains in **D1** when appropriate. Treating a **corrupt** or suspect manifest is **advanced operator** work (manual procedures), not a default end-user path. |
| **G4** | **Not in Phase 5:** no extension of **`--verbose`** (or similar) for SQLite “health hints” and **no** dedicated operator subsection for that — **deferred** / **won’t do** in this phase. |

### Section H — Environment and filesystem — **decided**

| ID | Decision |
|----|----------|
| **H1** | **Local vs network:** operator doc assumes **local** (or otherwise well-behaved POSIX) storage for the manifest DB as the **normal** case. **Network** paths (e.g. **NFS**, **SMB**, **cloud-backed** mounts) are **best-effort** — **not** labeled globally “unsupported,” but operators should expect extra **latency**, **locking**, and **coherency** risk; **not** recommended for the **active** manifest while **`backuper`** is writing. Cross-link **C3** (live sync / active `db/`) and contention / **`SQLITE_BUSY`** (**B**). |
| **H2** | **SQL examples / paths:** **minimum** note in operator doc — use **`sqlite3`** forms that handle **spaces** and **unusual** characters safely (e.g. **SQLite URI** / **`.open`** patterns as appropriate); **shell-escape** paths when passing them on the command line. **No** curated multi-example block required in Phase 5. |
| **H3** | **Read-only mount / container:** **one sentence** in **prerequisites** / environment (or equivalent) — the manifest DB **must** be on a **writable** path for the process; **read-only** mounts or read-only containers **prevent** normal operation. **No** dedicated subsection beyond that (**J2** may still list symptoms). |

### Section I — Operator configuration (manifest DB only) — **decided**

| ID | Decision |
|----|----------|
| **I1** | **Env var list:** **one subsection** in the **primary** Phase 5 operator doc — **table** or **bullet** list of manifest-related environment variables with **name**, **purpose**, **allowed values** (where applicable), and **default** / unset behavior (e.g. **`BACKUPER_SQLITE_SYNCHRONOUS`** per **A1**). **Discoverability** from README / contributor docs is **J3**, not a separate **I1** deliverable. |
| **I2** | **PRAGMA knobs vs env:** **`synchronous`** is the **only** manifest SQLite **PRAGMA** exposed via **environment variable** in Phase 5 (**A1**). **All other** PRAGMA-related behavior uses **code defaults** and is described under **A** / **ADR-0005** — **no** additional env tunables in this phase. Include a **short** “env vs code default” table (or equivalent) in the operator doc: **one row** for **`synchronous`** (**env**); remaining rows **code default / no env** (e.g. **`busy_timeout`** **5000 ms** **A2**, **`foreign_keys`**, **`journal_mode=WAL`**, etc., per locked policy in **A**). |

### Section J — Phase 5 documentation deliverables — **decided**

| ID | Decision |
|----|----------|
| **J1** | **One primary operator document:** a **single** Markdown file under **`docs/`** (exact filename chosen when Phase 5 docs are written). It aggregates **PRAGMA** / connection policy (**A**), **backup** / copy (**C**), **integrity** checks (**D1**), **env vars** (**I1**–**I2**), and **SQL** / **`sqlite3`** recipes (**E1**–**E2**) as **sections** or clearly delineated subsections — **not** split into multiple top-level operator docs for Phase 5. |
| **J2** | **Troubleshooting:** **compact** **symptom → cause → action** coverage — **table** or **short** subsections (**not** a long runbook). Include **`SQLITE_BUSY`** / contention (**B**), **non-writable** manifest path (**H3**), **`pending`** version after crash (**D3** / **ADR-0002**), **`user_version`** / schema mismatch (**D4**). For **corrupt** / suspect DB: point to **manifest file backup / restore** (**C**) and **`PRAGMA quick_check`** / **`integrity_check`** (**D1**); **no** dedicated **`SQLITE_CORRUPT`** playbook (**D2**); advanced manual recovery remains **G3**. |
| **J3** | **Discoverability:** add a **link** to the primary operator doc from the **README** and from **contributing** / **developer** documentation **and** from a **`docs/` index** (e.g. `docs/README.md` or equivalent) **if** such an index exists at implementation time — so the doc is findable from **multiple** entry points. |

### Section F — Performance and validation (“realistic manifest sizes”) — **not in Phase 5**

| ID | Decision |
|----|----------|
| **F1** | **Not in Phase 5:** no **reference workload** definition (versions × files × row shape) for “large” in operator docs or validation artifacts for this phase. |
| **F2** | **Not in Phase 5:** no prescribed **measurement** story (manifest I/O vs backup time, DB size growth, etc.) for Phase 5 deliverables. |
| **F3** | **Not in Phase 5:** no **acceptance bar** (numeric, qualitative, or fixture-based) for “validated for realistic sizes” in this execution scope. |
| **F4** | **Not in Phase 5:** no **commit-per-file-at-max-scale** operator narrative beyond what [**ADR-0005**](../adr/0005-sqlite-adapter-contract-and-schema-v1.md) already states; [issue #50](https://github.com/piazentin/backuper/issues/50) remains **separate** unless Phase 5 explicitly expands. |

**Note:** [`sqlite-support-assessment.md`](sqlite-support-assessment.md) still mentions **performance** validation as a Phase 5–family outcome; **reconcile** that document **separately** if this **no-F** scope stands.

### Section K — Validation and proof (Phase 5 claims) — **not in Phase 5**

| ID | Decision |
|----|----------|
| **K1** | **Not in Phase 5:** no **benchmark** script in-repo, **ad hoc** proof harness, or **CI** job framed as proving “validated for realistic sizes” — consistent with **F** being out of this execution scope. |
| **K2** | **Not in Phase 5:** no required **runbook spot-checks** or **tested-vs-written** matrix for the backup/integrity story in Phase 5 deliverables; operator guidance remains **documentation-first** for this phase. |

**Note:** **K** is **aligned** with **F** (**no** performance/validation bar); reconcile any **assessment** wording about **proof** or **benchmarks** **separately**.

---

## Pending questions — Phase 5 coverage checklist

Use as a **coverage list** for Phase 5 completion: each item is a decision, documentation gap, or validation gap **within Phase 5** only. **Sections A–C**, **E**, and **G**–**J** are fully reflected in the **decisions log** (**G4** explicitly **not in Phase 5**); **Section D** is **partial** (**D2** deferred — see decisions log); **Sections F** and **K** are **not in Phase 5** (**F1**–**F4**, **K1**–**K2** — see decisions log).

**Item IDs:** each bullet has an ID **`SectionLetter` + number** (e.g. **B3**, **D2**) for cross-reference in discussion and the decisions log.

### A. Durability, PRAGMAs, and connection defaults

- [x] **A1** — Ship **default `synchronous=NORMAL`** and **documented env override** (name, allowed values). *(See decisions log.)*
- [x] **A2** — **`busy_timeout`:** default **5000 ms** + document.
- [x] **A3** — **`wal_autocheckpoint`:** default; no extra doc.
- [x] **A4** — **`mmap_size`:** default.
- [x] **A5** — **`auto_vacuum`:** not required for Phase 5.
- [x] **A6** — **`temp_store` / temp file location** — one-line warning in ops.
- [x] **A7** — **Where to record** locked PRAGMA policy: **operator doc only**.
- [x] **A8** — **SQLite version** for CLI recipes: pin to **embedded floor** for supported Python.

### B. Contention, parallelism, and single-writer expectations

- [x] **B1** — **Supported model:** e.g. one writer per backup root, multiple readers — stated clearly for operators. *(B1 — see decisions log.)*
- [x] **B2** — **Concurrent `backuper` processes** against the same tree: expected error behavior and docs. *(B2 — doc only; GitHub issue for stronger behavior — see decisions log.)*
- [x] **B3** — **External tools** opening the DB read-only while `backuper` runs: allowed vs discouraged; risks. *(B3 — see decisions log.)*
- [x] **B4** — **`SQLITE_BUSY`:** user-visible guidance and whether the app retries. *(B4 — see decisions log.)*
- [x] **B5** — **Incomplete / unreadable SQLite manifest** during read operations: operator-facing recovery text (consistent with current CLI behavior, without expanding resolver policy here). *(B5 — ADR-0002 “pending” narrative; corrupt/missing → **D** — see decisions log.)*

### C. Backup, copy, replication, archival

- [x] **C1** — **Blessed procedure** to back up the manifest safely (quiesce / checkpoint / `.backup` / `Connection.backup` vs coordinated multi-file copy). *(C1 — `.backup` / `Connection.backup` default; multi-file or snapshot fallback — see decisions log.)*
- [x] **C2** — **Tree-level backups** that include `db/`: consistency and **stale WAL** risk. *(C2 — quiesce or consistent snapshot; warn on live copy — see decisions log.)*
- [x] **C3** — **Live sync** of the backup root (cloud sync, NFS, SMB): expectations and warnings. *(C3 — discourage active `db/` during writes; alternatives — see decisions log.)*
- [x] **C4** — **Race** when copying `*.sqlite3` + `-wal` + `-shm`; preference for `.backup`. *(C4 — see decisions log.)*
- [x] **C5** — **Snapshots** (e.g. ZFS, LVM): any extra guidance. *(C5 — brief snapshot note; portable copy → C1 — see decisions log.)*
- [x] **C6** — **`VACUUM` / checkpoint** as part of size or off-site copy strategy. *(C6 — optional `wal_checkpoint`; optional `VACUUM`; issue #50 out — see decisions log.)*

### D. Corruption, integrity, and recovery (SQLite manifest only)

- [x] **D1** — When and how to run **`PRAGMA integrity_check`** / **`quick_check`**; how to read results. *(D1 — when to run + `quick_check` vs full; read results — see decisions log.)*
- [ ] **D2** — **`SQLITE_CORRUPT`:** realistic recovery path using **manifest file backups** (no migration-era story here). *(**Deferred** — not in Phase 5 operator doc; see decisions log.)*
- [x] **D3** — **Pending version after crash:** operator narrative (re-run, cleanup, expectations) aligned with ADR-0002. *(D3 — see decisions log.)*
- [x] **D4** — **`user_version` / schema mismatch** on upgrade: operator-facing upgrade or fail-fast story. *(D4 — see decisions log.)*

### E. Export, query, audits, and privacy

- [x] **E1** — **Deliverable shape:** SQL recipes only vs CLI helper vs both. *(E1 — **SQL + `sqlite3` only**; **no** Phase 5 CLI helpers — see decisions log.)*
- [x] **E2** — **Example queries:** versions, file counts, hash-oriented reports, diffs between versions. *(E2 — curated examples + optional `pending` SQL — see decisions log.)*
- [x] **E3** — **Sensitive paths** in query output: warnings or redaction conventions. *(E3 — warning; no automated redaction — see decisions log.)*
- [x] **E4** — **Stable machine-readable output** (CSV/JSON): in Phase 5 vs deferred. *(E4 — **not in Phase 5** — see decisions log.)*

### F. Performance and validation (“realistic manifest sizes”)

- [x] **F1** — **Workload definition:** versions × files × row size for “large” in this product. *(**Not in Phase 5** — see decisions log.)*
- [x] **F2** — **What to measure:** manifest I/O overhead, DB size growth vs backup time. *(**Not in Phase 5** — see decisions log.)*
- [x] **F3** — **Acceptance bar:** numeric vs qualitative vs fixture-based regression. *(**Not in Phase 5** — see decisions log.)*
- [x] **F4** — **Commit-per-file** at max scale: document as acceptable vs triggers a follow-up (outside Phase 5 unless you widen scope); [issue #50](https://github.com/piazentin/backuper/issues/50) stays separate unless pulled in. *(**Not in Phase 5** — see decisions log; ADR-0005 + #50 unchanged.)*

### G. Observability and diagnostics

- [x] **G1** — **Logging:** which SQLite errors log at which level; avoid noise on expected conditions. *(G1 — **minimal** logging; avoid noise — see decisions log.)*
- [x] **G2** — **CLI exit codes / messages** for corruption vs usage errors (within Phase 5 touch surface). *(G2 — document + small normalization — see decisions log.)*
- [x] **G3** — **Optional preflight** `integrity_check` before read-heavy commands: in or out of scope. *(G3 — **out**; **`quick_check`** via **D1** only; no new CLI; advanced operators — see decisions log.)*
- [x] **G4** — **`--verbose` / docs** for health hints. *(**Not in Phase 5** — see decisions log.)*

### H. Environment and filesystem

- [x] **H1** — **Local vs network filesystems:** supported vs best-effort language. *(H1 — local assumed; network best-effort + risks; **C3**/**B** — see decisions log.)*
- [x] **H2** — **SQL examples:** path quoting for unusual characters. *(H2 — **minimum** URI/`.open`/shell note — see decisions log.)*
- [x] **H3** — **Read-only mount / container:** manifest DB must be writable — call out if relevant. *(H3 — **one sentence** writable path — see decisions log.)*

### I. Operator configuration (manifest DB only)

- [x] **I1** — **Env vars** for Phase 5 (e.g. `BACKUPER_SQLITE_SYNCHRONOUS`): single documented list. *(I1 — **one subsection** in primary operator doc — see decisions log; **J3** = discoverability.)*
- [x] **I2** — Whether any manifest PRAGMA knobs are **env-only** for this phase vs documented defaults only. *(I2 — **`synchronous`** only via env; short env vs code-default table — see decisions log.)*

### J. Phase 5 documentation deliverables

- [x] **J1** — **One primary operator doc** for the SQLite manifest: pragmas, backup, integrity, env vars, troubleshooting. *(J1 — **single** `docs/` Markdown file — see decisions log.)*
- [x] **J2** — **Troubleshooting:** symptom → cause → action (e.g. BUSY, corrupt, incomplete DB, wrong readiness for read). *(J2 — **compact** table/sections; **D2** out — see decisions log.)*
- [x] **J3** — **Link** from a discoverable place (e.g. README or contributor doc) to that operator doc. *(J3 — **README** + **contributing** + **`docs/` index** if present — see decisions log.)*

### K. Validation and proof (Phase 5 claims)

- [x] **K1** — **Benchmarks:** script in repo, ad hoc, or CI optional — what proves “validated for realistic sizes.” *(**Not in Phase 5** — see decisions log; aligns with **F**.)*
- [x] **K2** — **Runbook spot-checks:** how much of the backup/integrity story is **tested** vs **written**. *(**Not in Phase 5** — see decisions log.)*

---

## Resolved or parked (Phase 5 context)

| Topic | Status |
|-------|--------|
| Default `synchronous` | **A1:** **NORMAL** + env override — to ship in Phase 5 |
| `busy_timeout` default | **A2:** **5000 ms** — to ship + document |
| WAL + companion files | ADR-0001 — Phase 5 ops doc must explain safe backup |
| Async DB offload | Issue #50 — outside Phase 5 unless explicitly included |
| Concurrent `backuper` / locking UX | **B2:** doc in Phase 5; **link GitHub tracking issue** at ship time (stronger behavior later) |
| Corruption recovery playbook (`SQLITE_CORRUPT`, **D2**) | **D2:** **deferred** — not in Phase 5 operator doc; generic backup/restore (**C**) until a later iteration |
| Stable machine-readable manifest export (**E4**) | **E4:** **not in Phase 5** — no `backuper` CSV/JSON contract; no `sqlite3` export-mode stability promise |
| Performance / “realistic manifest sizes” (**F1**–**F4**) | **F1**–**F4:** **not in Phase 5** — no workload/metrics/acceptance/max-scale validation deliverables; reconcile [`sqlite-support-assessment.md`](sqlite-support-assessment.md) separately |
| Validation / proof (**K1**–**K2**) | **K1**–**K2:** **not in Phase 5** — no benchmark/CI proof or runbook tested-vs-written matrix; aligns with **F**; reconcile assessment separately |
| Verbose / health hints (**G4**) | **G4:** **not in Phase 5** — no `--verbose` health-hints extension or dedicated subsection |
| Network / non-local manifest paths (**H1**) | **H1:** **local** assumed; **network** best-effort — see **C3** / **B**; not a compatibility matrix |
| Manifest env / PRAGMA exposure (**I1**–**I2**) | **I1:** single list in operator doc; **I2:** **`synchronous`** env-only; other PRAGMAs **code defaults** + **A** |
| Phase 5 operator doc shell (**J1**–**J3**) | **J1:** one `docs/` file; **J2:** compact troubleshooting; **J3:** README + contributing + docs index |

---

## Document history

| Date | Change |
|------|--------|
| 2026-04-19 | Initial discovery note; expanded checklist; resolved/parked table. |
| 2026-04-19 | **Phase 5 scope only:** removed other phases, cross-phase items, and non–Phase 5 meta; checklist renumbered A–K. |
| 2026-04-19 | **Section A decided:** decisions log + checklist marked complete; `busy_timeout` 5000 ms; A3/A5/A6/A7/A8 as agreed. |
| 2026-04-19 | Checklist: **item IDs** A1–K2 + legend line for cross-reference. |
| 2026-04-19 | **Section B partial:** B1–B4 decided; B5 open; B2 doc-only + GitHub issue link at ship time. |
| 2026-04-19 | **Section B complete:** **B5** option 2 (ADR-0002 pending narrative; corrupt/missing deferred to **D**). |
| 2026-04-19 | **Section C decided:** backup/replication/archival (**C1**–**C6**); decisions log + checklist marked complete. |
| 2026-04-19 | **Section D partial:** **D1** (when to run + checks), **D3**, **D4** decided; **D2** **deferred** (not Phase 5); checklist **D2** left open. |
| 2026-04-19 | **Section E decided:** **E1** SQL/`sqlite3` only (no CLI helpers); **E2**–**E3** as agreed; **E4** **not in Phase 5** (stable CSV/JSON / `sqlite3` modes out of scope). |
| 2026-04-19 | **Section F not in Phase 5:** **F1**–**F4** explicitly out; checklist marked complete; note to reconcile assessment performance bullet separately. |
| 2026-04-19 | **Section K not in Phase 5:** **K1**–**K2** explicitly out (benchmarks / runbook proof); aligns with **F**; checklist marked complete. |
| 2026-04-19 | **Section G decided:** **G1** minimal logging / avoid noise; **G2** document + small CLI message/exit normalization; **G3** no preflight/no new CLI, **`quick_check`** via **D1**, corrupt = advanced ops; **G4** not in Phase 5 (`--verbose` health hints **won’t do**); checklist **G1**–**G4** marked; resolved/parked row for **G4**. |
| 2026-04-19 | **Section H decided:** **H1** local-first, network best-effort (**C3**/**B**); **H2** minimum path/quoting note for **`sqlite3`**; **H3** one-sentence writable manifest path; checklist **H1**–**H3** marked; resolved/parked row for **H1**. |
| 2026-04-19 | **Section I decided:** **I1** env-var subsection in primary operator doc (**J3** separate); **I2** **`synchronous`** only env-tunable PRAGMA + short env vs code-default table; checklist **I1**–**I2** marked; resolved/parked row for **I1**–**I2**. |
| 2026-04-19 | **Section J decided:** **J1** single primary `docs/` Markdown operator doc; **J2** compact troubleshooting (**D2** not in depth); **J3** links from README, contributing, and `docs/` index if present; checklist **J1**–**J3** marked; resolved/parked row for **J1**–**J3**. |
