from pathlib import Path
from uuid import UUID

import pytest
from backuper.components.csv_db import CsvBackupDatabase, CsvDb
from backuper.components.sqlite_db import SqliteBackupDatabase, SqliteDb
from backuper.config import CsvDbConfig, SqliteDbConfig
from backuper.models import BackedUpFileEntry, FileEntry, VersionNotFoundError
from backuper.ports import BackupDatabase


def _entry(
    *,
    relative_path: str,
    is_directory: bool,
    hash_value: str,
    stored_location: str,
    size: int,
    mtime: float,
    is_compressed: bool,
    backup_id: UUID,
) -> BackedUpFileEntry:
    return BackedUpFileEntry(
        source_file=FileEntry(
            path=Path(f"/src/{relative_path}"),
            relative_path=Path(relative_path),
            size=size,
            mtime=mtime,
            is_directory=is_directory,
        ),
        backup_id=backup_id,
        stored_location=stored_location,
        is_compressed=is_compressed,
        hash=hash_value,
    )


@pytest.fixture(params=["csv", "sqlite"])
def backup_database(request: pytest.FixtureRequest, tmp_path: Path) -> BackupDatabase:
    if request.param == "csv":
        return CsvBackupDatabase(CsvDb(CsvDbConfig(backup_dir=str(tmp_path))))
    return SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(tmp_path))))


@pytest.mark.asyncio
async def test_pending_versions_are_hidden_until_completed(
    backup_database: BackupDatabase,
) -> None:
    await backup_database.create_version("v-pending")

    assert await backup_database.list_versions() == []
    assert await backup_database.most_recent_version() is None
    with pytest.raises(VersionNotFoundError):
        await backup_database.get_version_by_name("v-pending")


@pytest.mark.asyncio
async def test_completed_version_is_discoverable_and_listed(
    backup_database: BackupDatabase,
) -> None:
    await backup_database.create_version("v-completed")
    await backup_database.complete_version("v-completed")

    assert await backup_database.list_versions() == ["v-completed"]
    assert await backup_database.get_version_by_name("v-completed") == "v-completed"
    assert await backup_database.most_recent_version() == "v-completed"


@pytest.mark.asyncio
async def test_list_files_returns_files_then_directories(
    backup_database: BackupDatabase,
) -> None:
    version = "v-order"
    await backup_database.create_version(version)
    await backup_database.add_file(
        version,
        _entry(
            relative_path="z.txt",
            is_directory=False,
            hash_value="hz",
            stored_location="data/z",
            size=2,
            mtime=2.0,
            is_compressed=False,
            backup_id=UUID("11111111-1111-1111-1111-111111111111"),
        ),
    )
    await backup_database.add_file(
        version,
        _entry(
            relative_path="adir",
            is_directory=True,
            hash_value="",
            stored_location="",
            size=0,
            mtime=0.0,
            is_compressed=False,
            backup_id=UUID("22222222-2222-2222-2222-222222222222"),
        ),
    )
    await backup_database.add_file(
        version,
        _entry(
            relative_path="a.txt",
            is_directory=False,
            hash_value="ha",
            stored_location="data/a",
            size=1,
            mtime=1.0,
            is_compressed=True,
            backup_id=UUID("33333333-3333-3333-3333-333333333333"),
        ),
    )
    await backup_database.complete_version(version)

    items = [item async for item in backup_database.list_files(version)]
    assert [item.relative_path for item in items] == [
        Path("z.txt"),
        Path("a.txt"),
        Path("adir"),
    ]
    assert [item.is_directory for item in items] == [False, False, True]
    assert [item.is_compressed for item in items[:2]] == [False, True]


@pytest.mark.asyncio
async def test_hash_and_metadata_lookups_for_completed_versions(
    backup_database: BackupDatabase,
) -> None:
    version = "v-lookups"
    entry = _entry(
        relative_path="doc.txt",
        is_directory=False,
        hash_value="h1",
        stored_location="data/doc",
        size=10,
        mtime=10.0,
        is_compressed=False,
        backup_id=UUID("44444444-4444-4444-4444-444444444444"),
    )
    await backup_database.create_version(version)
    await backup_database.add_file(version, entry)
    await backup_database.complete_version(version)

    by_hash = await backup_database.get_files_by_hash("h1")
    by_metadata = await backup_database.get_files_by_metadata(Path("doc.txt"), 10.0, 10)
    assert len(by_hash) == 1
    assert by_hash[0].stored_location == "data/doc"
    assert len(by_metadata) == 1
    assert by_metadata[0].source_file.relative_path == Path("doc.txt")
