from pathlib import Path

import pytest
from backuper.components.file_reader import LocalFileReader
from backuper.models import FileEntry
from backuper.ports import PathFilter


@pytest.mark.asyncio
async def test_local_file_reader():
    # Arrange
    test_dir = Path("test/resources/bkp_test_sources_new")
    # Empty directories are not tracked by git in CI checkouts, so ensure
    # the fixture directory exists before reading.
    (test_dir / "subdir" / "empty dir").mkdir(parents=True, exist_ok=True)
    reader = LocalFileReader()

    expected_files = {
        Path("LICENSE"): {"size": 1072, "is_directory": False},
        Path("text_file1.txt"): {"size": 217, "is_directory": False},
        Path("text_file1 copy.txt"): {"size": 217, "is_directory": False},
        Path("subdir"): {"size": 0, "is_directory": True},
        Path("subdir/starry_night.png"): {"size": 6466030, "is_directory": False},
        Path("subdir/empty dir"): {"size": 0, "is_directory": True},
    }

    # Act
    entries = []
    async for entry in reader.read_directory(test_dir):
        entries.append(entry)

    # Assert
    assert len(entries) == len(expected_files)

    for entry in entries:
        relative_path = entry.relative_path
        assert relative_path in expected_files

        expected = expected_files[relative_path]
        assert entry.size == expected["size"]
        assert entry.is_directory == expected["is_directory"]
        assert entry.path == test_dir / relative_path
        assert entry.mtime > 0


class _SelectivePathFilter(PathFilter):
    def __init__(self) -> None:
        self.prepared_roots: list[Path] = []

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        self.prepared_roots.append(walk_root)

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path not in {
            Path("skip.txt"),
            Path("ignored_dir"),
            Path("ignored_dir/child.txt"),
        }

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path == Path("ignored_dir")


@pytest.mark.asyncio
async def test_local_file_reader_applies_filter_with_safe_pruning_and_skip_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    # Arrange
    (tmp_path / "keep_dir").mkdir()
    (tmp_path / "ignored_dir").mkdir()
    (tmp_path / "keep_dir" / "keep.txt").write_text("keep", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("skip", encoding="utf-8")
    (tmp_path / "ignored_dir" / "child.txt").write_text("ignored", encoding="utf-8")
    path_filter = _SelectivePathFilter()
    reader = LocalFileReader(path_filter=path_filter)
    caplog.set_level("INFO")

    # Act
    entries = []
    async for entry in reader.read_directory(tmp_path):
        entries.append(entry.relative_path)

    # Assert
    assert sorted(entries) == [Path("keep_dir"), Path("keep_dir/keep.txt")]
    assert tmp_path in path_filter.prepared_roots
    assert (tmp_path / "ignored_dir") not in path_filter.prepared_roots
    messages = [record.getMessage() for record in caplog.records]
    assert any("Skipping ignored_dir (" in message for message in messages)
    assert any("Skipping skip.txt (" in message for message in messages)
    assert all("ignored_dir/child.txt" not in message for message in messages)


class _NonPruningExcludedDirectoryFilter(PathFilter):
    def __init__(self) -> None:
        self.prepared_roots: list[Path] = []

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        self.prepared_roots.append(walk_root)

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path != Path("ignored_dir")

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        return False


@pytest.mark.asyncio
async def test_local_file_reader_traverses_excluded_non_prunable_directory(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    # Arrange
    (tmp_path / "ignored_dir").mkdir()
    (tmp_path / "ignored_dir" / "child.txt").write_text("child", encoding="utf-8")
    path_filter = _NonPruningExcludedDirectoryFilter()
    reader = LocalFileReader(path_filter=path_filter)
    caplog.set_level("INFO")

    # Act
    entries = []
    async for entry in reader.read_directory(tmp_path):
        entries.append(entry.relative_path)

    # Assert
    assert Path("ignored_dir") not in entries
    assert Path("ignored_dir/child.txt") in entries
    assert (tmp_path / "ignored_dir") in path_filter.prepared_roots
    messages = [record.getMessage() for record in caplog.records]
    assert any("Skipping ignored_dir (" in message for message in messages)
