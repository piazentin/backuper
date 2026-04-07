"""CLI entry: ``uv run python -m scripts.migrate_version_csv``."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from scripts.migrate_version_csv.atomic_output import write_migrated_atomic
from scripts.migrate_version_csv.migrate import (
    MigrateError,
    migrate_version_csv_text,
    read_text,
)

_LOG = logging.getLogger(__name__)


def _discover_csv_files(backup_root: Path, db_dir: str) -> list[Path]:
    db_path = backup_root / db_dir
    if not db_path.is_dir():
        return []
    out: list[Path] = []
    for name in sorted(db_path.iterdir()):
        if not name.is_file():
            continue
        if name.name.startswith("."):
            continue
        if name.suffix != ".csv":
            continue
        out.append(name)
    return out


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Migrate version CSV manifests under a backup root to the canonical "
            "row shape. Run during a maintenance window when no backup command is active."
        )
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
        help="Directory under backup_root with content-addressed blobs (default: data)",
    )
    p.add_argument(
        "--csv",
        type=Path,
        action="append",
        default=None,
        help=(
            "Migrate a single manifest (path to …/db/<version>.csv). "
            "May be repeated. If omitted, all *.csv in db-dir are migrated."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes but do not write files",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging (e.g. progress per manifest)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if not args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    backup_root = args.backup_root.resolve()
    data_root = (backup_root / args.data_dir).resolve()

    if args.csv:
        targets = [p.resolve() for p in args.csv]
    else:
        targets = [p.resolve() for p in _discover_csv_files(backup_root, args.db_dir)]

    if not targets:
        print("No CSV files to migrate.", file=sys.stderr)
        return 0

    exit_code = 0
    for csv_path in targets:
        try:
            if args.verbose:
                _LOG.info("Migrating %s", csv_path)
            text = read_text(csv_path)
            migrated, warnings = migrate_version_csv_text(
                text,
                data_root=data_root,
                version_path=csv_path,
            )
            for w in warnings:
                _LOG.warning("%s", w)
            status = write_migrated_atomic(
                csv_path,
                migrated,
                dry_run=args.dry_run,
            )
            print(f"{csv_path}: {status}")
        except MigrateError as e:
            print(f"ERROR {e}", file=sys.stderr)
            exit_code = 1
        except OSError as e:
            print(f"ERROR {csv_path}: {e}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
