# Source ignores

This guide is for anyone configuring backups who needs **what to put where** without reading the full technical roadmap. Backuper applies **gitignore-style path patterns** under your backup **source** tree: ignored files and directories are **not** read for backup and **do not** appear in the version manifest CSV.

## On-disk rules

Place **`.gitignore`** and/or **`.backupignore`** files in directories inside the source tree. Patterns are **relative to that directory**, like Git. Nested directories can have their own files; rules from shallower directories still apply, with the usual layered precedence (see below).

When **both** `.gitignore` and `.backupignore` exist in the **same** directory, their pattern lines are combined in a **fixed filename order**: **`.backupignore` first, then `.gitignore`**.

Files are read as **UTF-8** (with BOM tolerated), **LF** or **CRLF** line endings; blank lines and **`#`** comments are skipped, same as Git.

## CLI rules (`new` / `update` only)

Without editing the tree you can pass extra rules:

- **`--ignore-pattern` `PATTERN`** (repeatable): one gitignore-style line per occurrence.
- **`--ignore-file` `PATH`** (repeatable): a file of gitignore-style lines (same line filtering as on-disk files).

**Merge order:** every `--ignore-pattern` in **argv order**, then each `--ignore-file` in **argv order** (lines from each file appended after all pattern flags). A relative **`PATH`** for `--ignore-file` is resolved against the **process current working directory**.

Together these form the **user** layer. **On-disk ignore files in the source tree have higher precedence** than this user layer when rules disagree—so tree rules can override or refine what you pass on the command line.

## How precedence works (short version)

Effective layers are applied from **broad to local**: user (CLI) patterns first, then ignore files from the source root down toward the path being evaluated, with **later matches winning** in gitignore fashion—including **`!`** negation that can re-include paths.

## Negation (`!`)

Lines starting with **`!`** can un-ignore paths that would otherwise be excluded. Negation interacts with **directory pruning** (whether the walker can skip whole subtrees): in edge cases Backuper may walk deeper than the minimum needed so that re-inclusion can be honored. For full detail, see **[source-ignore-rules-assessment.md](source-ignore-rules-assessment.md)**.

## Symlinks

Symbolic links to **directories** are **not** followed when walking the source (`followlinks=False`). The walk stays within the resolved source tree without descending through symlinked directories.

## Seeing what was skipped

By default, skipped entries are logged at **INFO** on stderr. The parenthetical names the **layer** that owned the winning rule: **`excluded by user`** for CLI `--ignore-pattern` / `--ignore-file` rules, or **`excluded by`** followed by the ignore file path **relative to the source root** (POSIX slashes), e.g. `.gitignore` or `pkg/.backupignore`.

```text
Skipping secrets/api.key (excluded by user)
Skipping build/tmp.o (excluded by .gitignore)
```

Use **`-q` / `--quiet`** before the subcommand to reduce informational logging. There is no separate “explain” or dry-run mode for `new` / `update` in the CLI today.

## What this does not affect

**`verify-integrity`** checks backup metadata and stored blobs under the backup root; it does **not** re-evaluate source ignore policy.

## Further reading

- **[source-ignore-rules-assessment.md](source-ignore-rules-assessment.md)** — layered semantics, roadmap context, and edge-case notes.
- Project layering and commands: **[AGENTS.md](../AGENTS.md)**.
- CLI overview: **[README.md](../README.md)**.
