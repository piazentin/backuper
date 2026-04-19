# Documentation

Project documentation that supplements **[README.md](../README.md)** (install, usage, dev commands) and **[AGENTS.md](../AGENTS.md)** (entrypoint, layering, tests, contribution map).

| Document | Description |
|----------|-------------|
| [csv-migration-contract.md](csv-migration-contract.md) | Required migration path for legacy version CSVs; canonical row contract for the runtime; migration script semantics (dry-run, apply, rollback artifacts) |
| [source-ignores.md](source-ignores.md) | Operator guide: on-disk `.gitignore` / `.backupignore`, CLI `--ignore-pattern` / `--ignore-file`, precedence vs the user layer, symlinks, logging, and negation edge cases |
| [sqlite-manifest-operations.md](sqlite-manifest-operations.md) | Operator guide: SQLite manifest PRAGMA defaults, env overrides, WAL concurrency, backup/integrity checks, curated `sqlite3` SQL, CLI exit behavior |
| [plans/](plans/) | Phased plans (e.g. SQLite manifest assessment) |
| [adr/](adr/) | Architecture decision records (**ADRs**), including SQLite manifest design |

Add new top-level docs here and link them from this table.
