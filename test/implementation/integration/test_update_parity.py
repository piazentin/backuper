"""
UPDATE-command parity tests: implementation `BackupController` vs legacy expectations.

Assertions mirror `test/legacy/test_backup.py` for `test_update_backup` and
`test_update_backup_with_zip` (data layout and DB rows for the update version).

Seeding matches legacy: `new` from `bkp_test_sources_new` as `test_new`, then
`update` from `bkp_test_sources_update` as `test_update`.

CSV written by the implementation for the update version must be readable by
**legacy** `CsvDb`. Separate tests run **legacy** `new` + `update` and assert the
implementation `CsvDb` can read that CSV (mixed-toolchain compatibility).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
    DirEntry,
    Version,
)
from backuper.implementation.components.file_reader import LocalFileReader
from backuper.implementation.components.filestore import LocalFileStore
from backuper.implementation.config import CsvDbConfig, FilestoreConfig
from backuper.implementation.controllers.backup import BackupController
import backuper.legacy.implementation.backup as legacy_backup
import backuper.legacy.implementation.config as legacy_config
from backuper.legacy.implementation.commands import NewCommand, UpdateCommand
from backuper.legacy.implementation.config import CsvDbConfig as LegacyCsvDbConfig
from backuper.legacy.implementation.csv_db import CsvDb as LegacyCsvDb
from backuper.legacy.implementation import models as legacy_models

import test.aux as aux
import test.aux.fixtures as fixtures

_REPO_ROOT = Path(__file__).resolve().parents[3]
_NEW_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_new"
_UPDATE_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_update"

# Same union as `BackupIntegrationTest.update_backup["hashes"]` in legacy tests.
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
    """Match legacy `BackupIntegrationTest.setUp` for UPDATE source."""
    _UPDATE_SOURCE.joinpath("LICENSE").touch(exist_ok=True)
    return _UPDATE_SOURCE


def _assert_stored_file_in_expected_set(
    stored_file: legacy_models.StoredFile,
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


def _assert_legacy_reader_matches_fixture(
    backup_dir: str, version_name: str, expected: dict
) -> None:
    legacy_db = LegacyCsvDb(LegacyCsvDbConfig(backup_dir=backup_dir))
    version = legacy_models.Version(version_name)
    dirs = legacy_db.get_dirs_for_version(version)
    assert set(dirs) == expected["dirs"]

    files = legacy_db.get_files_for_version(version)
    assert len(files) == len(expected["stored_files"])
    for stored_file in files:
        _assert_stored_file_in_expected_set(stored_file, expected["stored_files"])


async def _impl_new_backup_seed(
    destination: Path, new_src: Path, *, zip_enabled: bool
) -> None:
    d = str(destination)
    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=d)))
    controller = BackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(backup_dir=d, zip_enabled=zip_enabled)
        ),
    )
    await controller.new_backup(source=new_src, version="test_new")


def _assert_implementation_reader_matches_fixture(
    backup_dir: str, version_name: str, expected: dict
) -> None:
    impl_db = CsvDb(CsvDbConfig(backup_dir=backup_dir))
    version = Version(version_name)
    dirs = impl_db.get_dirs_for_version(version)
    expected_dirs = {DirEntry(d.name) for d in expected["dirs"]}
    assert {DirEntry(d.name) for d in dirs} == expected_dirs

    files = impl_db.get_files_for_version(version)
    assert len(files) == len(expected["stored_files"])
    for stored in files:
        if not any(
            stored.sha1hash == exp.sha1hash
            and stored.restore_path == exp.restore_path
            and stored.is_compressed == exp.is_compressed
            and stored.stored_location == exp.stored_location
            for exp in expected["stored_files"]
        ):
            raise AssertionError(
                f"No fixture match for implementation StoredFile {stored!r}"
            )


@pytest.fixture
def new_and_update_source_paths() -> tuple[Path, Path]:
    aux.rm_temp_dirs()
    yield (_prepare_new_source_tree(), _prepare_update_source_tree())
    aux.rm_temp_dirs()


@pytest.mark.asyncio
async def test_update_backup_parity_zip_disabled(
    tmp_path: Path, new_and_update_source_paths: tuple[Path, Path]
) -> None:
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "update_backup"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = BackupController(
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

    await controller.new_backup(source=new_src, version="test_new")
    await controller.add_version(source=upd_src, version="test_update")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name in _UPDATE_HASH_PATHS

    _assert_legacy_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup
    )


@pytest.mark.asyncio
async def test_update_backup_parity_zip_enabled(
    tmp_path: Path, new_and_update_source_paths: tuple[Path, Path]
) -> None:
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "update_backup_zip"
    destination.mkdir()

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = BackupController(
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

    await controller.new_backup(source=new_src, version="test_new")
    await controller.add_version(source=upd_src, version="test_update")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name.strip(".zip") in _UPDATE_HASH_PATHS

    _assert_legacy_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup_with_zip
    )


def test_legacy_update_written_csv_readable_by_implementation_zip_disabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", False)
    new_src, upd_src = new_and_update_source_paths
    destination = str(tmp_path / "legacy_update_zip_off")
    legacy_backup.new(
        NewCommand(
            "test_new",
            str(new_src),
            destination,
        )
    )
    legacy_backup.update(
        UpdateCommand(
            "test_update",
            str(upd_src),
            destination,
        )
    )
    _assert_implementation_reader_matches_fixture(
        destination, "test_update", fixtures.update_backup
    )


def test_legacy_update_written_csv_readable_by_implementation_zip_enabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", True)
    new_src, upd_src = new_and_update_source_paths
    destination = str(tmp_path / "legacy_update_zip_on")
    legacy_backup.new(
        NewCommand(
            "test_new",
            str(new_src),
            destination,
        )
    )
    legacy_backup.update(
        UpdateCommand(
            "test_update",
            str(upd_src),
            destination,
        )
    )
    _assert_implementation_reader_matches_fixture(
        destination, "test_update", fixtures.update_backup_with_zip
    )


@pytest.mark.asyncio
async def test_impl_update_after_legacy_seed_zip_disabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy `new` seeds the tree; implementation `add_version` must stay on-disk compatible."""
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", False)
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "mixed_legacy_seed"
    legacy_backup.new(
        NewCommand("test_new", str(new_src), str(destination)),
    )

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = BackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(backup_dir=str(destination), zip_enabled=False)
        ),
    )
    await controller.add_version(source=upd_src, version="test_update")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name in _UPDATE_HASH_PATHS

    _assert_legacy_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup
    )


@pytest.mark.asyncio
async def test_impl_update_after_legacy_seed_zip_enabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", True)
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "mixed_legacy_seed_zip"
    legacy_backup.new(
        NewCommand("test_new", str(new_src), str(destination)),
    )

    db = CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(destination))))
    controller = BackupController(
        file_reader=LocalFileReader(),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(backup_dir=str(destination), zip_enabled=True)
        ),
    )
    await controller.add_version(source=upd_src, version="test_update")

    data_root = destination / "data"
    data_filenames = aux.list_all_files_recursive(str(data_root))
    assert len(data_filenames) == len(_UPDATE_HASH_PATHS)
    for name in data_filenames:
        assert name.strip(".zip") in _UPDATE_HASH_PATHS

    _assert_legacy_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup_with_zip
    )


def test_legacy_update_after_impl_seed_csv_readable_zip_disabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Implementation `new_backup` seeds the tree; legacy `update` CSV must parse in implementation."""
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", False)
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "mixed_impl_seed"
    destination.mkdir()
    asyncio.run(_impl_new_backup_seed(destination, new_src, zip_enabled=False))

    legacy_backup.update(
        UpdateCommand("test_update", str(upd_src), str(destination)),
    )
    _assert_implementation_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup
    )


def test_legacy_update_after_impl_seed_csv_readable_zip_enabled(
    tmp_path: Path,
    new_and_update_source_paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", True)
    new_src, upd_src = new_and_update_source_paths
    destination = tmp_path / "mixed_impl_seed_zip"
    destination.mkdir()
    asyncio.run(_impl_new_backup_seed(destination, new_src, zip_enabled=True))

    legacy_backup.update(
        UpdateCommand("test_update", str(upd_src), str(destination)),
    )
    _assert_implementation_reader_matches_fixture(
        str(destination), "test_update", fixtures.update_backup_with_zip
    )
