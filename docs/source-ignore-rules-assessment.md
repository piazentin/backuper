# Source ignore rules (`.gitignore`-style): technical assessment and roadmap

This document proposes how **backuper** could ignore paths under a backup **source** tree using semantics close to **Git’s ignore layering**, while leaving room for **future non-path rules** (for example size or age predicates). It is a design and delivery plan, not an implementation commitment.

## Goals

- **Nested ignore files**: patterns in `subdir/.gitignore` (and equivalents) apply to paths under `subdir/`, using **paths relative to the ignore file’s directory**, like Git.
- **Multiple on-disk filenames**: treat several basenames (for example `.gitignore` and `.backupignore`) as the **same kind** of ignore source when they appear in the same directory.
- **Layered rule sources** with a clear **stack** from “broad” to “local”:
  - **User / tool configuration** rules scoped to the backup job (global to that run).
  - **Repository / source root** ignore files at the backup source root.
  - **Nested** ignore files deeper in the tree.
- **Extensibility**: first release focuses on **path patterns** compatible with common `.gitignore` syntax; later releases may add **predicates** (size, mtime windows, and similar) without rewriting the core pipeline.

Non-goals for an initial release (unless you explicitly expand scope):

- Teaching the CSV manifest about “ignored paths” (today manifests list what was backed up; ignored items simply never appear).
- Changing **restore** behavior (restore reads the manifest, not the live source tree).

## Current integration surface (codebase)

Today, `new` / `update` discover source files through `LocalFileReader.read_directory`, which wraps `os.walk` and yields every file and directory under the source root.

```10:41:src/backuper/components/file_reader.py
    async def read_directory(self, path: Path) -> AsyncGenerator[FileEntry, None]:
        for root, dirs, files in os.walk(path):
            root_path = Path(root)
            # ... yields FileEntry for each dir and file ...
```

A practical place to enforce ignores is **inside or immediately around** this walk:

- **Directory pruning**: when a directory is ignored (and not re-included by negated patterns), Git still *conceptually* skips the subtree; `os.walk` can drop names from `dirs` to avoid descending—**only** if the matcher can prove the entire subtree is excluded. That is an optimization; correctness can start with “filter each yielded path” even if it is slower on huge trees.
- **Analyzer / controller**: keeping matching in `FileReader` (or a dedicated filter in front of the analyzer stream) preserves the layering rule in **controllers** vs **components** described in `AGENTS.md`: introduce a **`ports.PathFilter`** (name illustrative) implemented in `components/`, constructed in the CLI wiring, optionally composed with `LocalFileReader`.

## Semantics: how stacking should work

### Path relativity (Git-compatible mental model)

- Patterns in `ROOT/.backupignore` are relative to `ROOT/` (the ignore file’s directory), not the process cwd.
- Patterns in `ROOT/a/b/.gitignore` apply to paths under `ROOT/a/b/` and are relative to that directory.
- A path being evaluated at `ROOT/a/b/c.txt` is tested against the **stack** of matchers anchored at each ancestor directory that contains one or more ignore files (plus the user-config layer).

### Layer ordering (precedence)

Git’s effective rule is: **later / more specific rules override earlier ones**, including **`!` negation** patterns. **Locked:** backuper uses **full Git-style** semantics here (negation and re-inclusion are in scope).

Stack (lowest → highest precedence; **higher wins** when rules conflict):

1. **User configuration** patterns (baseline for the run).
2. **Root-level** ignore files (`.gitignore`, `.backupignore`, … at the backup source root).
3. **Nested** ignore files from shallow to deep along the path (each directory’s files ordered deterministically—see below).

**Clarification vs “adding” rules:** nested files still **add** pattern lines, but because precedence matches Git, inner patterns (and `!` negation) can **override** broader layers—this is intentional for clarity and familiarity.

### Multiple filenames in one directory

When both `.gitignore` and `.backupignore` exist in the same directory:

- **Recommended**: concatenate pattern text in a **fixed, documented order** (for example alphabetical by basename: `.backupignore` then `.gitignore`) with an implicit newline boundary, then compile **one** matcher for that directory segment. [RECOMMENDATION ACCEPTED]
- **Document** that duplicate patterns are harmless; contradictory patterns resolve via normal Git-style last-wins behavior **within** that combined document (if negation is supported).

### Encoding and line endings

- Treat files as **UTF-8** with **LF or CRLF** newlines; ignore **BOM** if present.
- Ignore **blank lines** and **`#` comments** (Git-like).

### Symlinks

**Locked:** **do not follow** symlinked directories when walking the source tree (keep `os.walk(..., followlinks=False)`). Treat symlink entries according to that policy for both traversal and ignore matching (no descent through symlinked dirs; avoids escaping the declared source root via links).

## Library choice: `pathspec`

[`pathspec`](https://pypi.org/project/pathspec/) is a reasonable default for **Git wildmatch** style patterns (`gitwildmatch`), which matches what most users expect from `.gitignore`.

**Strengths**

- Mature pattern language: `**`, `*`, `?`, trailing dir slashes, negation, character classes—aligned with Git’s documentation users already know.
- Clear separation: compile patterns once, then test many relative paths.

**Caveats**

- **Performance**: compiling many pattern sets is fine; evaluating every file against the full ancestor stack is usually acceptable for typical trees. Profile before micro-optimizing; consider pruning `dirs` in `os.walk` once negation semantics are nailed down.
- **Git parity edge cases**: rare differences can exist versus the exact Git implementation; document “Git-like, powered by `pathspec`” rather than “bug-for-bug identical to Git”.
- **Future predicates** (size, date): `pathspec` is **path-only**. Plan an **adapter** that evaluates `(path, stat)` through a small internal interface so path rules and predicate rules share one pipeline.

**Alternatives** (brief)

- **Shell out to `git check-ignore`**: reuses Git’s engine but couples runtime to Git, complicates Windows sandboxes, and blurs semantics for non-Git trees.
- **Hand-rolled minimatcher**: cheap dependency-wise, expensive in correctness and maintenance.

## Extensible rule model (for later phases)

Introduce an internal concept such as `IgnoreDecision` / `FilterContext`:

- **Inputs**: `source_root: Path`, `candidate: FileEntry` (already carries `relative_path`, `size`, `mtime`, `is_directory`), optional `stat` for future fields.
- **Output**: `include` vs `exclude` plus optional `reason` for diagnostics/logging.

**Rule kinds (evolutionary)**

1. **Path rules** (phase 1): backed by `pathspec` pattern lists bound to anchor directories.
2. **Predicate rules** (later): examples you mentioned:
   - `size > N`, `size < N`
   - `mtime` older / newer than a boundary (absolute instant vs “now minus duration”)
3. **Composition**: ordered list of rule sources; each source contributes patterns and/or predicates. Final decision follows documented precedence.

**Syntax extension strategy**

- **Option A — new directives in the same files**: reserved prefixes, for example `[backuper]` sections or `size>1GiB` lines. This couples extensions to on-disk files and may surprise users who expect pure Git parsing.
- **Option B — sidecar TOML/YAML** (for example `.backuper/rules.toml`) for predicates, keeping `.gitignore` strictly Git-syntax. This is often easier to explain and validate.
- **Option C — predicates only in user config** (**locked** for predicates): tree `.gitignore` / `.backupignore` files stay Git-syntax-only; size/mtime-style rules live in user/tool config. **Future:** Option B (sidecar) may be added if operators outgrow C; Option A (inline extensions) is **out of scope** by decision.

## Phased roadmap

Phases are ordered for **risk reduction**: ship path ignores first, then performance, then richer rules.

### Phase 0 — Decisions and specification freeze

- Confirm [Locked decisions](#locked-decisions-summary) against implementation spikes (pathspec, `os.walk` behavior).
- Write a short **user-facing** section for `README.md` later (not required in this design doc).
- Define **default filenames** list in one constant (for example `(".gitignore", ".backupignore")`) with optional user override in config/CLI when you add that surface.

**Exit criteria**: agreed semantics document + example fixtures for tests.

**Validation**

- **Spec review**: this document’s semantics match spike conclusions (pathspec match results for a small hand-picked matrix; symlink `followlinks=False` documented).
- **Fixtures (design-time)**: list named scenarios you will need in Phase 1 (see [Per-phase validation and testing](#per-phase-validation-and-testing)) and add **empty fixture dirs / README stubs** under **`test/resources/`** (on-disk trees), not under `test/aux/`—so Phase 1 is not blocked on assets.
- **No production code yet** → no `make test` gate for Phase 0 itself; optional scratch spike stays off `main` or is deleted after merge.

### Phase 1 — Path-only ignores (correctness first) [COMPLETED]

- Add a **`PathFilter` port** (name to be chosen) with a single method such as `def allows(self, entry: FileEntry, *, source_root: Path) -> bool:` (sync is fine; heavy work is already on disk in the reader).
- Implement **loader**: discover ignore files while walking; cache compiled `pathspec` matchers per anchor directory.
- Wire into **`LocalFileReader`** (or a thin `FilteringFileReader` wrapper constructed in CLI wiring) so ignored paths never reach analysis / DB.
- **Logging (locked):** log at **INFO** for every path the filter excludes **that the walk actually evaluates**. When a **directory** is excluded and the walker **does not descend** into it (subtree skipped as a unit), log **once** for that directory—the **top** of the skipped subtree—not for each descendant (those paths are never visited). Skipped **files** (and dirs when they are leaf decisions without suppressed descent) still log one line each, with context (*why*: user rule vs path to the relevant ignore file). **Note:** one-line subtree logging **requires** suppressed descent for that directory; **Git-style negation** inside ignored parents can force descent for correctness, in which case descendants may be evaluated and logged individually if they are themselves skipped.

**Exit criteria**: `make test` green; integration proves manifest excludes ignored paths.

**Validation**

- **Automated**: `make lint` and `make test` (full suite for merge-quality; use `make unit` / `make integration` locally while iterating—see `AGENTS.md`).
- **Coverage**: new code in filter + reader wiring should be covered by **unit** tests; end-to-end behavior by **integration** tests on disk + CSV rows.
- **Observability**: at least one integration or unit test uses **logging capture** (`caplog` at INFO) to assert **subtree skip ⇒ single INFO** for the directory boundary and **file skip ⇒ one INFO** per file when descent is not suppressed.
- **Scenario matrix** (minimum): nested ignore file; two filenames merged in one dir; precedence **nested > root > (stub user if wired early)**; at least one **negation** case; symlinked dir **not** followed; UTF-8 + `#` comment line + blank line handling.

### Phase 2 — `os.walk` pruning and performance guardrails

- Prune `dirs` when entire subtrees are excluded **without** breaking negation semantics.
- Add lightweight timing logs or counters (files examined vs skipped) behind DEBUG or dedicated verbose flags if useful.

**Exit criteria**: documented performance expectations; no correctness regressions in integration tests (add cases with negation if supported).

**Validation**

- **Regression**: entire Phase 1 scenario matrix stays green unchanged in outcomes (same manifest rows / same inclusion set) unless a deliberate semantic fix is documented.
- **New tests**: cases where pruning **must not** apply (negation could un-ignore under a path that looked ignorable from the parent); cases where pruning **must** apply (pure subtree ignore).
- **Optional**: large synthetic tree test behind a **pytest marker** (e.g. `slow`) or local-only script documented in test module docstring—avoid flaking CI on timing assertions; prefer **counters** (“visited file count”) as hard assertions.

### Phase 3 — User configuration source

- Extend configuration (mechanism TBD: CLI flags, env, or config file) to accept **inline patterns** and/or **paths to extra pattern files**, merged as the lowest-precedence layer per your policy.
- Ensure deterministic ordering and stable error messages.

**Exit criteria**: users can ignore build artifacts globally without touching the source tree.

**Validation**

- **Integration**: user rules **lose** vs nested tree rules on conflict; user rules **win** vs nothing when no tree rule applies; malformed user input → stable **`UserFacingError`** / CLI usage surface (match existing CLI test style).
- **Unit**: argument parsing / config merge order (pure functions) with no disk I/O where possible.
- **Automated**: `make lint`; `make test`.

### Phase 4 — Predicate rules (size / mtime) behind a feature flag

- Introduce the **`FilterContext`** evaluation path.
- Parse predicate rules from **user / tool configuration only** (Option C); Option B may be layered later if needed.

**Exit criteria**: predicates are optional and isolated; path-only mode remains the default.

**Validation**

- **Flag off**: golden integration tests from Phases 1–3 produce **byte-identical manifests** (or identical CSV logical rows) compared to before Phase 4.
- **Flag on**: unit tests for **boundary** values (`==` threshold, just above/below); mtime tests use **injected clock** or `time.time` patching—avoid sleeping in CI.
- **Cross-OS**: at least one mtime/size test runs on **Linux + Windows** in CI if both are available; otherwise document manual matrix and keep assertions portable (integer size, second-resolution mtime expectations).
- **Automated**: `make lint`; `make test`.

### Phase 5 — Operational polish

- **`verify-integrity`**: **no change required** for ignore policy checks; keep integrity focused on backup tree state per `AGENTS.md`.
- **Dry-run / explain**: optional “why was this path skipped?” mode remains compatible with **INFO logs** for skipped paths (tune message shape so operators can grep logs or use a dedicated flag later).

**Validation**

- If new CLI flags or output modes ship: **integration** tests for stdout shape (stable keys/lines as the project does elsewhere); **no regression** on default quiet/non-dry-run behavior.
- **Manual smoke** checklist (release notes): run `new`/`update` on a small real tree, grep logs for expected single subtree line, confirm CSV excludes ignored paths.
- **Automated**: `make lint`; `make test`.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Precedence surprises vs Git | Document stack order; add integration fixtures copied from well-known Git examples. |
| Negation + pruning bugs | Ship pruning only with **negation + pruning** integration tests; Phase 1 may still **suppress descent** for subtree skips when semantics allow—tests must pin whether descendants are visited. |
| Escaping source root via symlinks | **Locked:** do not follow symlinks; document that symlink targets are not descended. |
| Predicate rules differ between OS/filesystems | Tests on Linux + macOS; document mtime precision (seconds vs subsecond). |

## Per-phase validation and testing

**Repo bar (any phase that merges code)** run **`make lint`** and **`make test`** before merge; use **`make unit`** / **`make integration`** for faster loops (`AGENTS.md`).

### Repo layout: `test/resources` vs `test/aux`

- **`test/resources/`** — checked-in **on-disk trees** (files and directories) used as static inputs, for example `bkp_test_sources_new` / `bkp_test_sources_update`. New ignore-rule **golden trees** should live here (or under a new sibling directory under `test/` if you outgrow the naming), with tests referencing them by stable `Path("test/resources/…")`-style paths.
- **`test/aux/`** — shared **Python helpers** (mocks, small builders), not a home for large directory fixtures. Keep using it for `MockFileReader`, `MockBackupDatabase`, and similar.

### Shared techniques

- **Golden trees**: small directories under **`test/resources/`** (see above) plus integration or unit tests that assert **on-disk layout** and **CSV rows** (existing repo pattern).
- **Logging assertions**: use pytest **`caplog`** at **INFO** for skip lines; assert **count** and **substring** (path + rule source), not full timestamps.
- **Symlinks**: one fixture with a symlinked directory proves the walker does **not** follow it (`followlinks=False`) and does not backup through it.
- **Windows**: prefer **forward slashes** in authored patterns in tests; add at least one test that uses `Path` normalization consistent with runtime (no hard-coded `\` unless testing Windows-only branch).

### Phase 0 — assets and checklist

| Item | Done when |
| --- | --- |
| Scenario list frozen | Every bullet under Phase 1 “Scenario matrix” has a matching **fixture name** or “N/A” rationale |
| Fixtures discoverable | `test/resources/...` paths documented in the test module or a README stub next to the tree |
| Spike discarded or promoted | Scratch `pathspec` script either deleted or converted into **unit** tests in Phase 1 |

### Phase 1 — minimum automated catalog

| ID | Automation | Asserts |
| --- | --- | --- |
| P1.1 | Unit | Patterns anchored to correct directory; relativity for nested `.gitignore` |
| P1.2 | Unit | Two filenames in one dir merged in **documented order**; duplicate lines harmless |
| P1.3 | Integration | Ignored **file** absent from CSV; **INFO** once for that skip |
| P1.4 | Integration | Ignored **directory subtree** absent from CSV; **INFO** once at directory boundary when descent suppressed |
| P1.5 | Integration | **Negation** re-includes a path under a broader ignore (may force descent—assert visit + log behavior explicitly) |
| P1.6 | Integration | **Precedence**: nested rule overrides root and user baseline (add user layer stub if Phase 3 not merged yet, or split test in Phase 3) |
| P1.7 | Integration | Symlink dir not followed |
| P1.8 | Unit | UTF-8 with BOM optional; `#` comments; blank lines |

### Phase 2 — pruning catalog

| ID | Automation | Asserts |
| --- | --- | --- |
| P2.1 | Integration | Same inclusion set / CSV as Phase 1 for identical fixtures (pruning is optimization-only) |
| P2.2 | Integration | Negation case that **must** descend still finds re-included file |
| P2.3 | Optional marked | Visited-node count drops for large ignored subtree (counter hook), no wall-clock threshold |

### Phase 3 — user config catalog

| ID | Automation | Asserts |
| --- | --- | --- |
| P3.1 | Integration | User ignore + tree ignore combined per precedence |
| P3.2 | Unit/CLI test | Invalid config path / invalid pattern file → stable error |
| P3.3 | Integration | Deterministic ordering: snapshot of “effective” debug output or sorted diagnostic list if exposed |

### Phase 4 — predicates catalog

| ID | Automation | Asserts |
| --- | --- | --- |
| P4.1 | Integration | Default/off: identical outputs to pre-predicate baseline |
| P4.2 | Unit | Size threshold boundaries; mtime boundaries with faked clock |
| P4.3 | Integration | Predicate + path rule interaction (AND semantics documented in test name) |

### Phase 5 — polish catalog

| ID | Automation | Asserts |
| --- | --- | --- |
| P5.1 | Integration (if shipped) | Explain/dry-run output stable; default command output unchanged without flag |
| P5.2 | Manual | Short smoke checklist executed and recorded in PR **Validation** section |

### Optional hardening (any later phase)

- **Property-based** tests for relativity invariants (hypothesis) if maintenance cost is acceptable.
- **Golden log** file comparison only if log format is treated as API; otherwise prefer substring assertions.

## Locked decisions (summary)

| Topic | Decision |
| --- | --- |
| Negation (`!pattern`) | **Full Git-style** (re-inclusion allowed). |
| Precedence | **Nested > root > user** (most specific wins). |
| Ignored directories | **Omit from manifest** (same parity as ignored files—not backed up, not listed). |
| Symlinks | **Do not follow** when walking the source tree. |
| Diagnostics | **INFO** for skips: **one line per skipped file**; for a **skipped subtree**, **one line at the top excluded directory** when descent is suppressed (descendants not visited ⇒ not logged). |
| Predicate rules location | **Option C** (user/tool config only); Option B allowed later if needed; **Option A rejected**. |
| Windows | **First-class** cross-OS behavior; document and test path pattern expectations. |
| Reproducibility / restore | **No extra snapshot** of effective ignores in the backup DB: ignore files live in the source tree and are **backed up like other files**; a full restore brings them back. |

---

**Related code today**: `LocalFileReader` (`src/backuper/components/file_reader.py`), backup orchestration in `src/backuper/controllers/backup.py`, CLI wiring in `src/backuper/entrypoints/cli/runner.py`.
