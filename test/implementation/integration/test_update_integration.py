"""
UPDATE-command integration tests: on-disk layout and CSV rows for `add_version`.

Seeding matches `new` from `bkp_test_sources_new` as `test_new`, then
`add_version` from `bkp_test_sources_update` as `test_update`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import test.aux as aux
import test.aux.fixtures as fixtures
from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
    StoredFile,
    Version,
)
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.backup import add_version, new_backup

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NEW_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_new"
_UPDATE_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_update"

_UPDATE_HASH_PATHS = {
    "/f/e/f/9/fef9161f9f9a492dba2b1357298f17897849fefc",
    "/0/7/c/8/07c8762861e8f1927708408702b1fd747032f050",
    "/1/0/e/4/10e4b6f822c7493e1aea22d15e515b584b2db7a2",
    "/7/f/2/f/7f2f5c0211b62cc0f2da98c3f253bba9dc535b17",
    "/5/b/5/1/5b5174193c004d8f27811b961fbaa545b5460f2a",
}


def _prepare_new_source_tree() -> Path:
    empty_dir = _NEW_SOURCE / "subdir" / "empty dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return _NEW_SOURCE


def _prepare_update_source_tree() -> Path:
    _UPDATE_SOURCE.joinpath("LICENSE").touch(exist_ok=True)
    return _UPDATE_SOURCE


def _assert_stored_file_in_expected_set(
    stored_file: StoredFile,
    expected_files: set,
) -> None:
    for expected in expected_files:
        if (
            expected.sha1hash == stored_file.sha1hash
            and expected.restore_path == stored_file.restore_path
            and expected.is_compressed == stored_file.is_compressed
            and expected.stored_location == stored_file.stored_location
        ):
            return
    raise AssertionError(
        f"StoredFile[{stored_file.restore_path!r}] not in expected set"
    )


def _assert_csv_reader_matches_fixture(
    backup_dir: str, version_name: str, expected: dict
) -> None:
    impl_db = CsvDb(CsvDbConfig(backup_dir=backup_dir))
    version = Version(version_name)
    dirs = impl_db.get_dirs_for_version(version)
    assert set(dirs) == expected["dirs"]

    files = impl_db.get_files_for_version(version)
    assert len(files) == len(expected["stored_files"])
    for stored_file in files:
        _assert_stored_file_in_expected_set(stored_file, expected["stored_files"])


@pytest.fixture
def new_and_update_source_paths() -> tuple[Path, Path]:
    aux.rm_temp_dirs()
    yield (_prepare_new_source_tree(), _prepare_update_source_tree())
    aux.rm_temp_dirs()


@pytest.mark.asyncio
async def test_update_backup_integration_zip_disabled(
    tmp_path: Path, new_and_update_source_paths: tuple[Path, Path]
) -> None:
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "update_backup"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(destination),
            zip_enabled=False,
        )
    )
    await new_backup(
        new_src,
        "test_new",
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )
    await add_version(
        upd_src,
        "test_update",
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name in _UPDATE_HASH_PATHS

    _assert_csv_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup
    )


@pytest.mark.asyncio
async def test_update_backup_integration_zip_enabled(
    tmp_path: Path, new_and_update_source_paths: tuple[Path, Path]
) -> None:
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "update_backup_zip"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    filestore = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(destination),
            zip_enabled=True,
        )
    )
    await new_backup(
        new_src,
        "test_new",
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )
    await add_version(
        upd_src,
        "test_update",
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=filestore,
    )

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name.strip(".zip") in _UPDATE_HASH_PATHS

    _assert_csv_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup_with_zip
    )
