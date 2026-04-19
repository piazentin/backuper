from pathlib import Path
from uuid import UUID

import pytest
from backuper.components.csv_db import (
    CsvBackupDatabase,
    CsvDb,
    _csvrow_to_model,
    _StoredFile,
    _Version,
)
from backuper.config import CsvDbConfig
from backuper.models import BackedUpFileEntry, FileEntry, MalformedBackupCsvError


def test_csvrow_to_model_uses_first_seven_columns_when_row_is_longer() -> None:
    row = [
        "f",
        "docs/readme.txt",
        "abc",
        "0/1/2/3/abc",
        "False",
        "10",
        "1.0",
        "extra",
        "ignored",
    ]
    m = _csvrow_to_model(row)
    assert isinstance(m, _StoredFile)
    assert m.restore_path == "docs/readme.txt"
    assert m.sha1hash == "abc"
    assert m.stored_location == "0/1/2/3/abc"
    assert m.is_compressed is False
    assert m.size == 10
    assert m.mtime == 1.0


def test_csvrow_to_model_rejects_short_file_rows() -> None:
    with pytest.raises(MalformedBackupCsvError):
        _csvrow_to_model(["f", "a.txt", "hashonly"])


def test_csvrow_to_model_rejects_non_integer_size() -> None:
    row = ["f", "a.txt", "abc", "0/1/2/3/abc", "False", "not-int", "1.0"]
    with pytest.raises(MalformedBackupCsvError, match="size field"):
        _csvrow_to_model(row)


def test_csvrow_to_model_rejects_non_float_mtime() -> None:
    row = ["f", "a.txt", "abc", "0/1/2/3/abc", "False", "10", "bad"]
    with pytest.raises(MalformedBackupCsvError, match="mtime field"):
        _csvrow_to_model(row)


@pytest.mark.asyncio
async def test_csv_backup_database_ignores_appledouble_sidecar_csv(
    tmp_path: Path,
) -> None:
    """macOS may create `._<name>.csv` AppleDouble files; they must not be versions."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    # AppleDouble-ish binary (not valid UTF-8 CSV)
    (db_dir / "._2023-01-07T182558.csv").write_bytes(
        b"\x00\x05\x16\x07" + b"\x00" * 100
    )

    await db.create_version("2023-01-07T182558")
    await db.complete_version("2023-01-07T182558")

    assert await db.list_versions() == ["2023-01-07T182558"]

    # Must not raise UnicodeDecodeError when scanning versions
    assert await db.get_files_by_metadata(Path("nope.txt"), 0.0, 0) == []


@pytest.mark.asyncio
async def test_csv_backup_database_create_version_and_list_versions(
    tmp_path: Path,
) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)

    await db.create_version("2026.03.29")
    await db.create_version("v.scsv")
    await db.complete_version("2026.03.29")
    await db.complete_version("v.scsv")

    assert await db.list_versions() == ["2026.03.29", "v.scsv"]


@pytest.mark.asyncio
async def test_csv_backup_database_list_versions_lexicographic_not_dir_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-0003: list_versions sorts; order does not follow get_all_versions iteration."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    await db.create_version("z-version")
    await db.create_version("a-version")
    await db.complete_version("z-version")
    await db.complete_version("a-version")

    def unsorted_get_all_versions(self: CsvDb) -> list[_Version]:
        return [_Version("z-version"), _Version("a-version")]

    monkeypatch.setattr(CsvDb, "get_all_versions", unsorted_get_all_versions)

    assert await db.list_versions() == ["a-version", "z-version"]


@pytest.mark.asyncio
async def test_csv_backup_database_add_and_lookup_file_entries(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    await db.create_version("20260329000000")

    file_entry = FileEntry(
        path=Path("/src/docs/readme.txt"),
        relative_path=Path("docs/readme.txt"),
        size=42,
        mtime=1711700000.123,
        is_directory=False,
    )
    stored_file = BackedUpFileEntry(
        source_file=file_entry,
        backup_id=UUID("11111111-1111-1111-1111-111111111111"),
        stored_location="data/f1",
        is_compressed=False,
        hash="abc123",
    )
    second_file_entry = FileEntry(
        path=Path("/src/docs/notes.txt"),
        relative_path=Path("docs/notes.txt"),
        size=12,
        mtime=1711700001.0,
        is_directory=False,
    )
    second_stored_file = BackedUpFileEntry(
        source_file=second_file_entry,
        backup_id=UUID("33333333-3333-3333-3333-333333333333"),
        stored_location="data/f2",
        is_compressed=False,
        hash="def456",
    )

    await db.add_file("20260329000000", stored_file)
    await db.add_file("20260329000000", second_stored_file)
    await db.complete_version("20260329000000")

    by_metadata = await db.get_files_by_metadata(
        Path("docs/readme.txt"), 1711700000.123, 42
    )
    assert len(by_metadata) == 1
    assert by_metadata[0].stored_location == "data/f1"
    assert by_metadata[0].hash == "abc123"
    assert by_metadata[0].source_file.relative_path == Path("docs/readme.txt")

    by_hash = await db.get_files_by_hash("abc123")
    assert len(by_hash) == 1
    assert by_hash[0].source_file.relative_path == Path("docs/readme.txt")

    second_by_metadata = await db.get_files_by_metadata(
        Path("docs/notes.txt"), 1711700001.0, 12
    )
    assert len(second_by_metadata) == 1
    assert second_by_metadata[0].stored_location == "data/f2"
    assert second_by_metadata[0].hash == "def456"
    assert second_by_metadata[0].source_file.relative_path == Path("docs/notes.txt")

    second_by_hash = await db.get_files_by_hash("def456")
    assert len(second_by_hash) == 1
    assert second_by_hash[0].source_file.relative_path == Path("docs/notes.txt")


@pytest.mark.asyncio
async def test_csv_backup_database_add_and_list_directory_entries(
    tmp_path: Path,
) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    await db.create_version("20260329010000")

    dir_entry = BackedUpFileEntry(
        source_file=FileEntry(
            path=Path("/src/subdir"),
            relative_path=Path("subdir"),
            size=0,
            mtime=0.0,
            is_directory=True,
        ),
        backup_id=UUID("22222222-2222-2222-2222-222222222222"),
        stored_location="",
        is_compressed=False,
        hash="",
    )
    await db.add_file("20260329010000", dir_entry)
    await db.complete_version("20260329010000")

    items = []
    async for item in db.list_files("20260329010000"):
        items.append(item)

    assert len(items) == 1
    assert items[0].is_directory is True
    assert items[0].relative_path == Path("subdir")


@pytest.mark.asyncio
async def test_csv_backup_database_writes_and_appends_csv_rows(tmp_path: Path) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    version = "20260329020000"

    await db.create_version(version)
    csv_file = tmp_path / "db" / f"{version}.csv"
    pending_csv_file = tmp_path / "db" / f".pending__{version}.csv"
    assert not csv_file.exists()
    assert pending_csv_file.exists()
    assert pending_csv_file.read_text(encoding="utf-8") == ""

    first = BackedUpFileEntry(
        source_file=FileEntry(
            path=Path("/src/a.txt"),
            relative_path=Path("a.txt"),
            size=10,
            mtime=111.0,
            is_directory=False,
        ),
        backup_id=UUID("44444444-4444-4444-4444-444444444444"),
        stored_location="data/a",
        is_compressed=False,
        hash="ha",
    )
    second = BackedUpFileEntry(
        source_file=FileEntry(
            path=Path("/src/b.txt"),
            relative_path=Path("b.txt"),
            size=20,
            mtime=222.0,
            is_directory=False,
        ),
        backup_id=UUID("55555555-5555-5555-5555-555555555555"),
        stored_location="data/b",
        is_compressed=False,
        hash="hb",
    )

    await db.add_file(version, first)
    content_after_first = pending_csv_file.read_text(encoding="utf-8")
    lines_after_first = [line for line in content_after_first.splitlines() if line]
    assert len(lines_after_first) == 1
    assert '"f","a.txt","ha","data/a","False","10","111.0"' in content_after_first

    await db.add_file(version, second)
    content_after_second = pending_csv_file.read_text(encoding="utf-8")
    lines_after_second = [line for line in content_after_second.splitlines() if line]
    assert len(lines_after_second) == 2
    assert '"f","a.txt","ha","data/a","False","10","111.0"' in content_after_second
    assert '"f","b.txt","hb","data/b","False","20","222.0"' in content_after_second

    await db.complete_version(version)
    assert not pending_csv_file.exists()
    assert csv_file.exists()


@pytest.mark.asyncio
async def test_csv_backup_database_pending_version_hidden_from_listing_and_most_recent(
    tmp_path: Path,
) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)

    await db.create_version("v-pending")

    assert await db.list_versions() == []
    assert await db.most_recent_version() is None


@pytest.mark.asyncio
async def test_csv_backup_database_complete_version_renames_pending_manifest(
    tmp_path: Path,
) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    version = "v-finalize"

    await db.create_version(version)
    pending_csv_file = tmp_path / "db" / f".pending__{version}.csv"
    final_csv_file = tmp_path / "db" / f"{version}.csv"
    assert pending_csv_file.exists()
    assert not final_csv_file.exists()

    await db.complete_version(version)

    assert not pending_csv_file.exists()
    assert final_csv_file.exists()
    assert await db.list_versions() == [version]
    assert await db.most_recent_version() == version


@pytest.mark.asyncio
async def test_csv_backup_database_keeps_pending_manifest_when_not_completed(
    tmp_path: Path,
) -> None:
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    version = "v-failed"

    await db.create_version(version)
    await db.add_file(
        version,
        BackedUpFileEntry(
            source_file=FileEntry(
                path=Path("/src/failed.txt"),
                relative_path=Path("failed.txt"),
                size=10,
                mtime=1.0,
                is_directory=False,
            ),
            backup_id=UUID("66666666-6666-6666-6666-666666666666"),
            stored_location="data/fail",
            is_compressed=False,
            hash="hfail",
        ),
    )

    pending_csv_file = tmp_path / "db" / f".pending__{version}.csv"
    final_csv_file = tmp_path / "db" / f"{version}.csv"
    assert pending_csv_file.exists()
    assert not final_csv_file.exists()
    assert await db.list_versions() == []


@pytest.mark.asyncio
async def test_csv_backup_database_list_files_single_csv_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """list_files must scan the version CSV once (no separate get_files + get_dirs passes)."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    version = "20260329030000"
    await db.create_version(version)
    await db.complete_version(version)

    def fail_if_legacy_double_read(*_args, **_kwargs) -> None:
        raise AssertionError(
            "list_files must not call get_files_for_version or get_dirs_for_version"
        )

    monkeypatch.setattr(csv_db, "get_files_for_version", fail_if_legacy_double_read)
    monkeypatch.setattr(csv_db, "get_dirs_for_version", fail_if_legacy_double_read)

    fs_calls: list[str] = []
    real_get_fs = CsvDb.get_fs_objects_for_version

    def track_get_fs(self: CsvDb, ver) -> list:
        fs_calls.append(ver.name)
        return real_get_fs(self, ver)

    monkeypatch.setattr(CsvDb, "get_fs_objects_for_version", track_get_fs)

    items: list[FileEntry] = []
    async for item in db.list_files(version):
        items.append(item)

    assert fs_calls == [version]
    assert items == []


@pytest.mark.asyncio
async def test_csv_backup_database_list_files_mixed_rows_yield_files_then_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All file entries (in CSV order among `f` rows) then all dirs (CSV order among `d`)."""
    csv_db = CsvDb(CsvDbConfig(backup_dir=str(tmp_path)))
    db = CsvBackupDatabase(csv_db)
    version = "20260329040000"
    await db.create_version(version)
    csv_file = tmp_path / "db" / f"{version}.csv"
    csv_file.write_text(
        '"d","first_dir",""\n'
        '"f","z.txt","hz","lz","False","1","1.0"\n'
        '"d","second_dir",""\n'
        '"f","a.txt","ha","la","False","2","2.0"\n',
        encoding="utf-8",
    )

    def fail_if_legacy_double_read(*_args, **_kwargs) -> None:
        raise AssertionError(
            "list_files must not call get_files_for_version or get_dirs_for_version"
        )

    monkeypatch.setattr(csv_db, "get_files_for_version", fail_if_legacy_double_read)
    monkeypatch.setattr(csv_db, "get_dirs_for_version", fail_if_legacy_double_read)

    items: list[FileEntry] = []
    async for item in db.list_files(version):
        items.append(item)

    assert len(items) == 4
    assert [i.relative_path for i in items[:2]] == [Path("z.txt"), Path("a.txt")]
    assert not items[0].is_directory and not items[1].is_directory
    assert items[0].hash == "hz" and items[1].hash == "ha"
    assert [i.relative_path for i in items[2:]] == [
        Path("first_dir"),
        Path("second_dir"),
    ]
    assert items[2].is_directory and items[3].is_directory
