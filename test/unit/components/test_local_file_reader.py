from pathlib import Path

import pytest
from backuper.components.file_reader import LocalFileReader
from backuper.components.path_ignore import GitIgnorePathFilter
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
        self.source_roots: list[Path] = []

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        self.prepared_roots.append(walk_root)
        self.source_roots.append(source_root)

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path not in {
            Path("skip.txt"),
            Path("ignored_dir"),
            Path("ignored_dir/child.txt"),
        }

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path == Path("ignored_dir")


@pytest.mark.asyncio
async def test_local_file_reader_gitignore_caplog_user_and_tree_exclusion_substrings(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Skip logs include grep-friendly reasons: CLI patterns vs on-disk ignore files."""
    (tmp_path / "by_user.txt").write_text("u", encoding="utf-8")
    (tmp_path / "by_tree.txt").write_text("t", encoding="utf-8")
    (tmp_path / "kept.txt").write_text("k", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("by_tree.txt\n", encoding="utf-8")
    reader = LocalFileReader(
        path_filter=GitIgnorePathFilter(user_patterns=("by_user.txt",)),
    )
    caplog.set_level("INFO", logger="backuper.components.file_reader")

    paths: list[Path] = []
    async for entry in reader.read_directory(tmp_path):
        paths.append(entry.relative_path)

    assert sorted(paths) == [Path(".gitignore"), Path("kept.txt")]
    messages = [record.getMessage() for record in caplog.records]
    user_logs = [msg for msg in messages if "Skipping by_user.txt" in msg]
    tree_logs = [msg for msg in messages if "Skipping by_tree.txt" in msg]
    assert len(user_logs) == 1
    assert "excluded by user" in user_logs[0]
    assert len(tree_logs) == 1
    assert "excluded by .gitignore" in tree_logs[0]


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
        self.source_roots: list[Path] = []

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        self.prepared_roots.append(walk_root)
        self.source_roots.append(source_root)

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return entry.relative_path != Path("ignored_dir")

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        return False


class _IgnoreSubtreeFilter(PathFilter):
    def __init__(self, *, prune: bool) -> None:
        self._prune = prune

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        return None

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        parts = entry.relative_path.parts
        return not parts or parts[0] != "ignored_dir"

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        return self._prune and entry.relative_path == Path("ignored_dir")


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


@pytest.mark.asyncio
@pytest.mark.slow
async def test_local_file_reader_walk_metrics_show_pruning_reduces_visited_nodes(
    tmp_path: Path,
):
    # Arrange
    ignored_dir = tmp_path / "ignored_dir"
    ignored_dir.mkdir()
    for index in range(200):
        (ignored_dir / f"child_{index}.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")

    pruning_reader = LocalFileReader(
        path_filter=_IgnoreSubtreeFilter(prune=True),
        collect_walk_metrics=True,
    )
    non_pruning_reader = LocalFileReader(
        path_filter=_IgnoreSubtreeFilter(prune=False),
        collect_walk_metrics=True,
    )

    # Act
    async for _ in pruning_reader.read_directory(tmp_path):
        pass
    async for _ in non_pruning_reader.read_directory(tmp_path):
        pass

    # Assert
    pruning_metrics = pruning_reader.get_last_walk_metrics()
    non_pruning_metrics = non_pruning_reader.get_last_walk_metrics()
    assert pruning_metrics is not None
    assert non_pruning_metrics is not None
    assert pruning_metrics.visited_entries < non_pruning_metrics.visited_entries
    assert pruning_metrics.pruned_directories == 1
    assert non_pruning_metrics.pruned_directories == 0


@pytest.mark.asyncio
async def test_local_file_reader_handles_dot_source_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "child.txt").write_text("child", encoding="utf-8")
    reader = LocalFileReader()
    monkeypatch.chdir(tmp_path)

    # Act
    entries = []
    async for entry in reader.read_directory(Path(".")):
        entries.append(entry.relative_path)

    # Assert
    assert Path("subdir") in entries
    assert Path("subdir/child.txt") in entries


@pytest.mark.asyncio
async def test_local_file_reader_passes_normalized_roots_to_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Arrange
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "child.txt").write_text("child", encoding="utf-8")
    path_filter = _SelectivePathFilter()
    reader = LocalFileReader(path_filter=path_filter)
    monkeypatch.chdir(tmp_path)

    # Act
    async for _ in reader.read_directory(Path(".")):
        pass

    # Assert
    normalized_root = tmp_path.absolute()
    assert normalized_root in path_filter.prepared_roots
    assert path_filter.source_roots
    assert all(
        source_root == normalized_root for source_root in path_filter.source_roots
    )
