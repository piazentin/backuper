"""CLI entry: ``uv run python -m scripts.migrate_manifest_csv_to_sqlite``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from backuper.models import MalformedBackupCsvError

from scripts.migrate_manifest_csv_to_sqlite.canonical_parse import (
    parse_canonical_version_csv,
)
from scripts.migrate_manifest_csv_to_sqlite.discovery import discover_csv_manifests

_LOG = logging.getLogger(__name__)

_RUNBOOK_EPILOG = """\
Runbook: docs/csv-to-sqlite-migration.md (TBD — operator guide will land with Phase 4).
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


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if not args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    backup_root = args.backup_root.resolve()

    if args.csv:
        targets = [p.resolve() for p in args.csv]
    else:
        targets = [
            p.resolve() for p in discover_csv_manifests(backup_root, args.db_dir)
        ]

    if not targets:
        print("No CSV manifest files found.", file=sys.stderr)
        return 0

    for csv_path in targets:
        try:
            parse_canonical_version_csv(csv_path)
        except MalformedBackupCsvError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.verbose:
        _LOG.info(
            "backup_root=%s db_dir=%s data_dir=%s",
            backup_root,
            args.db_dir,
            args.data_dir,
        )
        _LOG.info("--force=%s --dry-run=%s", args.force, args.dry_run)
        for csv_path in targets:
            _LOG.info("manifest: %s", csv_path)

    # Migration/staging/archive logic is implemented in follow-up tasks.
    if args.dry_run:
        print("Dry-run: would migrate the following manifests (no writes):")
        for csv_path in targets:
            print(f"  {csv_path}")
        return 0

    print(
        "ERROR: CSV→SQLite migration is not implemented in this build yet.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
