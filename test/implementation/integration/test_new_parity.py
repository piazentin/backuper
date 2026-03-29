"""
NEW-command parity tests: implementation `CreateBackupController` vs legacy expectations.

Assertions mirror `test/legacy/test_backup.py` for `test_new_backup` and
`test_new_backup_with_zip` (data layout and CSV DB contents).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
    DirEntry,
    StoredFile,
    Version,
)
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.create_backup import CreateBackupController
from backuper.legacy.implementation import models as legacy_models

import test.aux as aux
import test.aux.fixtures as fixtures

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NEW_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_new"

_NEW_HASH_PATHS = {
    "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
    "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
}


def _prepare_new_source_tree() -> Path:
    """Match legacy `BackupIntegrationTest.setUp` for NEW-related paths."""
    empty_dir = _NEW_SOURCE / "subdir" / "empty dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return _NEW_SOURCE


def _assert_stored_file_matches_legacy(
    actual: StoredFile, expected: legacy_models.StoredFile
) -> bool:
    return (
        actual.sha1hash == expected.sha1hash
        and actual.restore_path == expected.restore_path
        and actual.is_compressed == expected.is_compressed
        and actual.stored_location == expected.stored_location
    )


def _assert_db_matches_legacy_fixture(
    csv_db: CsvDb,
    version_name: str,
    expected: dict,
) -> None:
    version = Version(version_name)
    dirs = csv_db.get_dirs_for_version(version)
    expected_dirs = {DirEntry(d.name) for d in expected["dirs"]}
    assert {DirEntry(d.name) for d in dirs} == expected_dirs

    files = csv_db.get_files_for_version(version)
    assert len(files) == len(expected["stored_files"])
    for stored in files:
        if not any(
            _assert_stored_file_matches_legacy(stored, exp)
            for exp in expected["stored_files"]
        ):
            raise AssertionError(
                f"No legacy-equivalent StoredFile for {stored.restore_path!r}: {stored!r}"
            )


@pytest.fixture
def new_source_path() -> Path:
    aux.rm_temp_dirs()
    yield _prepare_new_source_tree()
    aux.rm_temp_dirs()


@pytest.mark.asyncio
async def test_new_backup_parity_zip_disabled(
    tmp_path: Path, new_source_path: Path
) -> None:
    destination = tmp_path / "new_backup"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = CreateBackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(destination),
                zip_enabled=False,
            )
        ),
    )

    await controller.create_backup(source=new_source_path, version="testing")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_NEW_HASH_PATHS)
    for name in data_filenames:
        assert name in _NEW_HASH_PATHS

    _assert_db_matches_legacy_fixture(
        CsvDb(CsvDbConfig(str(destination))),
        "testing",
        fixtures.new_backup_db,
    )


@pytest.mark.asyncio
async def test_new_backup_parity_zip_enabled(
    tmp_path: Path, new_source_path: Path
) -> None:
    destination = tmp_path / "new_backup_zip"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = CreateBackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(destination),
                zip_enabled=True,
            )
        ),
    )

    await controller.create_backup(source=new_source_path, version="testing")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_NEW_HASH_PATHS)
    for name in data_filenames:
        assert name.strip(".zip") in _NEW_HASH_PATHS

    _assert_db_matches_legacy_fixture(
        CsvDb(CsvDbConfig(str(destination))),
        "testing",
        fixtures.new_backup_with_zip_db,
    )
