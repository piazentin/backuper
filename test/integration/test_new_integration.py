"""
NEW-command integration tests: on-disk layout and manifest rows for `new_backup`.

Assertions mirror the former `test/legacy/test_backup.py` coverage for
`test_new_backup` and `test_new_backup_with_zip` (data layout and manifest rows).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import test.aux as aux
import test.aux.fixtures as fixtures
from backuper.components.backup_analyzer import BackupAnalyzerImpl
from backuper.components.file_reader import LocalFileReader
from backuper.components.filestore import LocalFileStore
from backuper.components.path_ignore import GitIgnorePathFilter
from backuper.components.reporter import NoOpAnalysisReporter
from backuper.components.sqlite_db import SqliteBackupDatabase, SqliteDb
from backuper.config import FilestoreConfig, SqliteDbConfig
from backuper.controllers.backup import new_backup

_REPO_ROOT = Path(__file__).resolve().parents[2]
_NEW_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_new"

_NEW_HASH_PATHS = {
    "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
    "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
}


def _copy_new_source_tree(tmp_path: Path) -> Path:
    """Copy the checked-in NEW fixture into tmp_path and ensure expected dirs exist."""
    dest = tmp_path / "bkp_test_sources_new"
    shutil.copytree(_NEW_SOURCE, dest, dirs_exist_ok=True)
    empty_dir = dest / "subdir" / "empty dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return dest


@pytest.fixture
def new_source_path(tmp_path: Path) -> Path:
    yield _copy_new_source_tree(tmp_path)


@pytest.mark.asyncio
async def test_new_backup_integration_zip_disabled(
    tmp_path: Path, new_source_path: Path
) -> None:
    destination = tmp_path / "new_backup"
    destination.mkdir()

    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(destination))))
    await new_backup(
        new_source_path,
        "testing",
        file_reader=LocalFileReader(path_filter=GitIgnorePathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(destination),
                zip_enabled=False,
            )
        ),
        reporter=NoOpAnalysisReporter(),
    )

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_NEW_HASH_PATHS)
    for name in data_filenames:
        assert name in _NEW_HASH_PATHS

    fixtures.assert_sqlite_manifest_matches_fixture(
        destination, "testing", fixtures.new_backup_db
    )


@pytest.mark.asyncio
async def test_new_backup_integration_zip_enabled(
    tmp_path: Path, new_source_path: Path
) -> None:
    destination = tmp_path / "new_backup_zip"
    destination.mkdir()

    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(destination))))
    await new_backup(
        new_source_path,
        "testing",
        file_reader=LocalFileReader(path_filter=GitIgnorePathFilter()),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(destination),
                zip_enabled=True,
            )
        ),
        reporter=NoOpAnalysisReporter(),
    )

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_NEW_HASH_PATHS)
    for name in data_filenames:
        assert name.removesuffix(".zip") in _NEW_HASH_PATHS

    fixtures.assert_sqlite_manifest_matches_fixture(
        destination, "testing", fixtures.new_backup_with_zip_db
    )
