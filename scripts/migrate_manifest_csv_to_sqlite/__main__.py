"""CLI entry: ``uv run python -m scripts.migrate_manifest_csv_to_sqlite``."""

from __future__ import annotations

import argparse
import logging
import secrets
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from backuper.components.sqlite_db import (
    SQL_INSERT_DIRECTORY,
    SQL_INSERT_FILE,
    SQL_INSERT_VERSION,
    SqliteDb,
)
from backuper.config import sqlite_db_config
from backuper.models import MalformedBackupCsvError

from scripts.migrate_manifest_csv_to_sqlite.canonical_parse import (
    CanonicalCsvDir,
    CanonicalCsvFile,
    parse_canonical_version_csv,
)
from scripts.migrate_manifest_csv_to_sqlite.created_at import (
    infer_created_at_for_manifests,
)
from scripts.migrate_manifest_csv_to_sqlite.discovery import discover_csv_manifests

_LOG = logging.getLogger(__name__)
_LIVE_SQLITE_FILENAME = "manifest.sqlite3"
_STAGING_SQLITE_SUFFIX = ".migrating"
_VERSION_STATE_COMPLETED = "completed"
_CSV_ARCHIVE_DIRNAME = "_migrated_from_csv"

_RUNBOOK_EPILOG = """\
Runbook: docs/csv-to-sqlite-migration.md
Run during a maintenance window when no backup command is active. After migration,
run verify-integrity and optionally restore as documented in the runbook.
"""


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Build manifest.sqlite3 from canonical version CSV manifests under a "
            "backup root. Run during a maintenance window when no backup command is active."
        ),
        epilog=_RUNBOOK_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "backup_root",
        type=Path,
        help="Root directory of the backup (contains db/ and data/ by default)",
    )
    p.add_argument(
        "--db-dir",
        default="db",
        help="Directory under backup_root with version CSV files (default: db)",
    )
    p.add_argument(
        "--data-dir",
        default="data",
        help=(
            "Directory under backup_root with content-addressed blobs (default: data)"
        ),
    )
    p.add_argument(
        "--csv",
        type=Path,
        action="append",
        default=None,
        help=(
            "Migrate a single manifest (path to …/db/<version>.csv). "
            "May be repeated. If omitted, all *.csv in db-dir are discovered."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report planned actions without staging, publishing, or archiving",
    )
    p.add_argument(
        "--validate",
        action="store_true",
        help=(
            "With --dry-run: read and validate every CSV manifest first (slower; "
            "catches malformed data). Ignored without --dry-run."
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Allow rebuild when live manifest.sqlite3 already exists",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging",
    )
    return p.parse_args(argv)


def _staging_sidecar_paths(staging_db_path: Path) -> tuple[Path, Path]:
    return (
        Path(f"{staging_db_path}-wal"),
        Path(f"{staging_db_path}-shm"),
    )


def _cleanup_staging_artifacts(staging_db_path: Path) -> None:
    wal_path, shm_path = _staging_sidecar_paths(staging_db_path)
    for candidate in (staging_db_path, wal_path, shm_path):
        if candidate.exists():
            candidate.unlink()


def _new_archive_run_id() -> str:
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}Z_{secrets.token_hex(4)}"


def _archive_migrated_csv_manifests(
    *, targets: list[Path], db_path: Path, archive_dirname: str = _CSV_ARCHIVE_DIRNAME
) -> Path:
    archive_parent = db_path / archive_dirname
    last_err: OSError | None = None
    for _ in range(16):
        archive_root = archive_parent / _new_archive_run_id()
        try:
            archive_root.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError as exc:
            last_err = exc
    else:
        assert last_err is not None
        raise RuntimeError(
            "Could not allocate a unique CSV archive directory under "
            f"{archive_parent} after repeated attempts."
        ) from last_err
    for csv_path in targets:
        destination = archive_root / csv_path.name
        if destination.exists():
            raise RuntimeError(
                "Archive collision while moving CSV manifest: "
                f"{destination} already exists."
            )
        csv_path.replace(destination)
    return archive_root


def _validate_explicit_csv_targets(*, targets: list[Path], db_path: Path) -> str | None:
    for csv_path in targets:
        if csv_path.name.startswith("."):
            return (
                "ERROR: --csv must not name a dot-prefixed file "
                f"({csv_path}); those are not migrated manifests."
            )
        if csv_path.suffix != ".csv":
            return f"ERROR: --csv entries must end with .csv; got {csv_path}."
        try:
            csv_path.relative_to(db_path)
        except ValueError:
            return f"ERROR: --csv paths must be inside {db_path}; got {csv_path}."

    seen: set[str] = set()
    duplicates: set[str] = set()
    for csv_path in targets:
        name = csv_path.name
        if name in seen:
            duplicates.add(name)
        seen.add(name)
    if duplicates:
        return (
            "ERROR: duplicate --csv basenames are not allowed because archival "
            "uses filename-only destinations: "
            f"{', '.join(sorted(duplicates))}"
        )

    return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if not args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    backup_root = args.backup_root.resolve()
    db_path = (backup_root / args.db_dir).resolve()
    data_path = (backup_root / args.data_dir).resolve()

    if args.csv:
        targets = [p.resolve() for p in args.csv]
        explicit_error = _validate_explicit_csv_targets(
            targets=targets, db_path=db_path
        )
        if explicit_error is not None:
            print(explicit_error, file=sys.stderr)
            return 1
    else:
        targets = [
            p.resolve() for p in discover_csv_manifests(backup_root, args.db_dir)
        ]

    if not targets:
        print("No CSV manifest files found.", file=sys.stderr)
        return 0

    live_db_path = db_path / _LIVE_SQLITE_FILENAME
    staging_db_path = db_path / f"{_LIVE_SQLITE_FILENAME}{_STAGING_SQLITE_SUFFIX}"

    if args.verbose:
        _LOG.info(
            "backup_root=%s db_dir=%s data_dir=%s",
            backup_root,
            args.db_dir,
            args.data_dir,
        )
        _LOG.info(
            "--force=%s --dry-run=%s --validate=%s",
            args.force,
            args.dry_run,
            args.validate,
        )
        for csv_path in targets:
            _LOG.info("manifest: %s", csv_path)

    if args.dry_run:
        if args.validate:
            for csv_path in targets:
                try:
                    parse_canonical_version_csv(csv_path)
                except MalformedBackupCsvError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 1
        print("Dry-run: would migrate the following manifests (no writes):")
        for csv_path in targets:
            print(f"  {csv_path}")
        return 0

    if args.validate:
        print(
            "ERROR: --validate is only meaningful with --dry-run.",
            file=sys.stderr,
        )
        return 1

    inferred_created_at = infer_created_at_for_manifests(targets)
    created_at_by_manifest = {
        item.manifest_path.resolve(): item.created_at for item in inferred_created_at
    }

    if not data_path.exists() or not data_path.is_dir():
        print(
            f"ERROR: data directory does not exist under backup root: {data_path}",
            file=sys.stderr,
        )
        return 1

    if live_db_path.exists() and not args.force:
        print(
            "ERROR: live SQLite manifest already exists at "
            f"{live_db_path}. Refusing to overwrite without --force.",
            file=sys.stderr,
        )
        return 1

    sqlite_cfg = sqlite_db_config(str(backup_root))
    sqlite_cfg.backup_db_dir = args.db_dir
    sqlite_cfg.sqlite_filename = staging_db_path.name

    try:
        _cleanup_staging_artifacts(staging_db_path)
        sqlite_db = SqliteDb(sqlite_cfg)
        with sqlite_db.connect() as conn:
            for csv_path in targets:
                try:
                    fs_objects = parse_canonical_version_csv(csv_path)
                except MalformedBackupCsvError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    raise
                version_name = csv_path.stem
                created_at = created_at_by_manifest[csv_path]
                conn.execute(
                    SQL_INSERT_VERSION,
                    (version_name, _VERSION_STATE_COMPLETED, created_at),
                )
                for entry in fs_objects:
                    if isinstance(entry, CanonicalCsvFile):
                        conn.execute(
                            SQL_INSERT_FILE,
                            (
                                version_name,
                                entry.restore_path,
                                "sha1",
                                entry.sha1hash,
                                entry.stored_location,
                                "zip" if entry.is_compressed else "none",
                                entry.size,
                                entry.mtime,
                            ),
                        )
                for entry in fs_objects:
                    if isinstance(entry, CanonicalCsvDir):
                        conn.execute(SQL_INSERT_DIRECTORY, (version_name, entry.name))
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        db_path.mkdir(parents=True, exist_ok=True)
        # Do not unlink the live DB before replace: if replace fails, the old
        # manifest must remain. os.replace overwrites the destination atomically.
        staging_db_path.replace(live_db_path)
        live_wal = Path(f"{live_db_path}-wal")
        live_shm = Path(f"{live_db_path}-shm")
        for sidecar in (live_wal, live_shm):
            if sidecar.exists():
                sidecar.unlink()
        _cleanup_staging_artifacts(staging_db_path)
    except Exception as exc:
        _cleanup_staging_artifacts(staging_db_path)
        print(f"ERROR: failed to build SQLite manifest: {exc}", file=sys.stderr)
        return 1

    try:
        with sqlite3.connect(live_db_path) as live_conn:
            live_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as exc:
        print(
            "WARNING: SQLite manifest was published but live WAL checkpoint failed: "
            f"{exc}. Run verify-integrity; if needed, open the DB and run "
            "PRAGMA wal_checkpoint(TRUNCATE).",
            file=sys.stderr,
        )

    try:
        _archive_migrated_csv_manifests(
            targets=targets,
            db_path=db_path,
        )
    except Exception as exc:
        print(
            "WARNING: CSV archival failed after SQLite publish; manifest.sqlite3 "
            f"is active at {live_db_path}. Move or archive the CSV manifests "
            f"manually if needed: {exc}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
