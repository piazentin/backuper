# Backuper

Very simple backup utility

## Architecture and migration

New development targets [`backuper/implementation`](backuper/implementation): entrypoints act as the composition root, controllers are function-only orchestration with explicit dependencies, and legacy code is phased out. For boundaries, routing, env flags, and tests, see **[AGENTS.md](AGENTS.md)**.

## Usage

Create a new backup:

```
python3 -m backuper new ~/backup/source/dir ~/backup/destination/dir
```

Update existing backup:

```
python3 -m backuper update ~/backup/source/dir ~/backup/destination/dir
```

Check backup integrity:

```
python3 -m backuper check ~/backup/destination/dir
```

`check` is a fast integrity/existence pass over backup metadata and stored blobs.
If a future deeper validation mode is added (for example full content/hash verification),
it should be exposed as a separate `verify` command rather than changing `check` semantics.

Restore a backup to a location:

```
restore --from /backup/source --to /backup/destination --version backup-version
```


## Run tests

```
make test
make test-implementation
make test-coverage
```

## Format and lint

Check everything (format, Ruff lint, import boundaries):

```
make lint
```

Apply Ruff formatting and auto-fixes:

```
make lint-fix
```

Format only (writes files):

```
make format
```
