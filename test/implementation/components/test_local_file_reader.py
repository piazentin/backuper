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
            "hash": "10e4b6f822c7493e1aea22d15e515b584b2db7a2",
            "is_directory": False
        },
        "text_file1.txt": {
            "size": 217,
            "hash": "fef9161f9f9a492dba2b1357298f17897849fefc",
            "is_directory": False
        },
        "text_file1 copy.txt": {
            "size": 217,
            "hash": "fef9161f9f9a492dba2b1357298f17897849fefc",
            "is_directory": False
        },
        "subdir": {
            "size": 0,
            "hash": None,
            "is_directory": True
        },
        "subdir/starry_night.png": {
            "size": 6466030,
            "hash": "07c8762861e8f1927708408702b1fd747032f050",
            "is_directory": False
        },
        "subdir/empty dir": {
            "size": 0,
            "hash": None,
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
        assert entry.hash == expected["hash"]
        assert entry.is_directory == expected["is_directory"]
        assert entry.path == test_dir / relative_path
        assert entry.mtime > 0
