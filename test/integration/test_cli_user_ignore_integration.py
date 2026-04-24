"""Integration: CLI runner applies merged user ignore patterns to manifests."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from backuper.commands import NewCommand
from backuper.config import SqliteDbConfig
from backuper.entrypoints.cli import run_new

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IGNORE_FIXTURE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_ignore_rules"


def _manifest_sqlite(backup: Path) -> Path:
    cfg = SqliteDbConfig(backup_dir=str(backup))
    return backup / cfg.backup_db_dir / cfg.sqlite_filename


def _manifest_paths(backup: Path, version: str) -> set[Path]:
    db_path = _manifest_sqlite(backup)
    with sqlite3.connect(db_path) as conn:
        files = {
            Path(r[0])
            for r in conn.execute(
                "SELECT restore_path FROM version_files WHERE version_name = ?",
                (version,),
            )
        }
        dirs = {
            Path(r[0])
            for r in conn.execute(
                "SELECT restore_path FROM version_directories WHERE version_name = ?",
                (version,),
            )
        }
    return files | dirs


def _copy_ignore_fixture(tmp_path: Path) -> Path:
    destination = tmp_path / "bkp_test_sources_ignore_rules"
    shutil.copytree(_IGNORE_FIXTURE, destination)
    return destination


def test_run_new_user_ignore_patterns_match_direct_filter(tmp_path: Path) -> None:
    source = _copy_ignore_fixture(tmp_path)
    destination = tmp_path / "backup"
    version = "cli-ignore"
    run_new(
        NewCommand(
            version,
            str(source),
            str(destination),
            ignore_patterns=("user_override/**", "layered_dir/**"),
        )
    )
    paths = _manifest_paths(destination, version)
    assert Path("user_override/kept_by_root.txt") in paths
    assert Path("layered_dir/outer.txt") in paths
    assert Path("layered_dir/inner.txt") not in paths


def test_run_new_user_ignore_file_equivalent(tmp_path: Path) -> None:
    source = _copy_ignore_fixture(tmp_path)
    extra = tmp_path / "extra.ignore"
    extra.write_text(
        "user_override/**\nlayered_dir/**\n",
        encoding="utf-8",
    )
    destination = tmp_path / "backup"
    version = "cli-ignore-file"
    run_new(
        NewCommand(
            version,
            str(source),
            str(destination),
            ignore_files=(str(extra),),
        )
    )
    paths = _manifest_paths(destination, version)
    assert Path("user_override/kept_by_root.txt") in paths
    assert Path("layered_dir/outer.txt") in paths
    assert Path("layered_dir/inner.txt") not in paths
