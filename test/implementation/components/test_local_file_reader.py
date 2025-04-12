import os
import pytest
from pathlib import Path
from backuper.implementation.components.file_reader import LocalFileReader

@pytest.mark.asyncio
async def test_local_file_reader():
    # Arrange
    test_dir = Path("test/resources/bkp_test_sources_new")
    reader = LocalFileReader()
    
    expected_files = {
        "LICENSE": {
            "size": 1072,
            "is_directory": False
        },
        "text_file1.txt": {
            "size": 217,
            "is_directory": False
        },
        "text_file1 copy.txt": {
            "size": 217,
            "is_directory": False
        },
        "subdir": {
            "size": 0,
            "is_directory": True
        },
        "subdir/starry_night.png": {
            "size": 6466030,
            "is_directory": False
        },
        "subdir/empty dir": {
            "size": 0,
            "is_directory": True
        }
    }

    # Act
    entries = []
    async for entry in reader.read_directory(test_dir):
        entries.append(entry)

    # Assert
    assert len(entries) == len(expected_files)

    for entry in entries:
        relative_path = str(entry.relative_path)
        assert relative_path in expected_files
        
        expected = expected_files[relative_path]
        assert entry.size == expected["size"]
        assert entry.is_directory == expected["is_directory"]
        assert entry.path == test_dir / relative_path
        assert entry.mtime > 0
