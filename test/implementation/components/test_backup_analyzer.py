import os
import pytest
from pathlib import Path
from typing import AsyncIterator
from uuid import UUID

from backuper.implementation.components.backup_analyzer import BackupAnalyzerImpl
from backuper.implementation.interfaces import FileEntry, BackupedFileEntry
from test.aux.mock_backup_database import MockBackupDatabase


async def async_iter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_backup_analyzer():
    # Arrange
    test_dir = Path("test/resources/bkp_test_sources_new")

    # Create test file entries
    file_entries = [
        FileEntry(
            path=test_dir / "LICENSE",
            relative_path=Path("LICENSE"),
            size=1072,
            mtime=1234567890.0,
            is_directory=False,
        ),
        FileEntry(
            path=test_dir / "text_file1.txt",
            relative_path=Path("text_file1.txt"),
            size=217,
            mtime=1234567890.0,
            is_directory=False,
        ),
        FileEntry(
            path=test_dir / "subdir",
            relative_path=Path("subdir"),
            size=0,
            mtime=0.0,
            is_directory=True,
        ),
        FileEntry(
            path=test_dir / "subdir/starry_night.png",
            relative_path=Path("subdir/starry_night.png"),
            size=6466030,
            mtime=1234567890.0,
            is_directory=False,
        ),
    ]

    # Create mock database with some files already backed up
    license_file = FileEntry(
        path=test_dir / "LICENSE",
        relative_path=Path("LICENSE"),
        size=1072,
        mtime=1234567890.0,
        is_directory=False,
    )

    text_file = FileEntry(
        path=test_dir / "text_file1.txt",
        relative_path=Path("text_file1.txt"),
        size=217,
        mtime=1234567890.0,
        is_directory=False,
    )

    mock_db = MockBackupDatabase(
        files_by_metadata={
            ("LICENSE", 1072, 1234567890.0): BackupedFileEntry(
                source_file=license_file,
                backup_id=UUID("12345678-1234-5678-1234-567812345678"),
                stored_location="/path/to/stored/file",
                is_compressed=False,
                hash="10e4b6f822c7493e1aea22d15e515b584b2db7a2",
            )
        },
        files_by_hash={
            "fef9161f9f9a492dba2b1357298f17897849fefc": [
                BackupedFileEntry(
                    source_file=text_file,
                    backup_id=UUID("12345678-1234-5678-1234-567812345678"),
                    stored_location="/path/to/stored/file",
                    is_compressed=False,
                    hash="fef9161f9f9a492dba2b1357298f17897849fefc",
                )
            ]
        },
    )

    # Create the analyzer
    analyzer = BackupAnalyzerImpl()

    # Act
    analyzed_entries = []
    async for entry in analyzer.analyze_stream(async_iter(file_entries), mock_db):
        analyzed_entries.append(entry)

    # Assert
    assert len(analyzed_entries) == 4

    # Check LICENSE file - should be marked as already backed up via metadata match
    license_entry = next(
        e for e in analyzed_entries if e.source_file.relative_path == Path("LICENSE")
    )
    assert license_entry.already_backed_up is True
    assert license_entry.backup_id is not None
    assert license_entry.hash == "10e4b6f822c7493e1aea22d15e515b584b2db7a2"

    # Check text_file1.txt - should be marked as already backed up via hash match
    text_file_entry = next(
        e
        for e in analyzed_entries
        if e.source_file.relative_path == Path("text_file1.txt")
    )
    assert text_file_entry.already_backed_up is True
    assert text_file_entry.backup_id is not None
    assert text_file_entry.hash == "fef9161f9f9a492dba2b1357298f17897849fefc"

    # Check subdir - should be marked as not backed up (directory)
    subdir_entry = next(
        e for e in analyzed_entries if e.source_file.relative_path == Path("subdir")
    )
    assert subdir_entry.already_backed_up is False
    assert subdir_entry.backup_id is None
    assert subdir_entry.hash is None

    # Check starry_night.png - should be marked as not backed up (new file)
    starry_night_entry = next(
        e
        for e in analyzed_entries
        if e.source_file.relative_path == Path("subdir/starry_night.png")
    )
    assert starry_night_entry.already_backed_up is False
    assert starry_night_entry.backup_id is None
    assert starry_night_entry.hash == "07c8762861e8f1927708408702b1fd747032f050"
