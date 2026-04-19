from pathlib import Path

from backuper.components.path_ignore import GitIgnorePathFilter, IgnoreMatchResolution
from backuper.models import FileEntry


def _entry(
    source_root: Path, relative_path: str, *, is_directory: bool = False
) -> FileEntry:
    path = source_root / relative_path
    return FileEntry(
        path=path,
        relative_path=Path(relative_path),
        size=0,
        mtime=0.0,
        is_directory=is_directory,
    )


def test_gitignore_patterns_are_anchored_to_nested_directory(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    nested = source_root / "nested"
    nested.mkdir(parents=True)
    (nested / ".gitignore").write_text("inner.txt\n", encoding="utf-8")

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(nested, source_root=source_root)

    assert (
        path_filter.allows(
            _entry(source_root, "nested/inner.txt"), source_root=source_root
        )
        is False
    )
    assert (
        path_filter.allows(_entry(source_root, "inner.txt"), source_root=source_root)
        is True
    )


def test_ignore_file_names_are_merged_in_alphabetical_basename_order(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".backupignore").write_text("target.txt\n", encoding="utf-8")
    (source_root / ".gitignore").write_text("!target.txt\n", encoding="utf-8")

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)

    assert (
        path_filter.allows(_entry(source_root, "target.txt"), source_root=source_root)
        is True
    )


def test_ignore_files_support_bom_comments_blank_lines_and_crlf(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text(
        "\ufeff# ignored comment\r\n\r\nignored.txt\r\n",
        encoding="utf-8",
    )

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)

    assert (
        path_filter.allows(_entry(source_root, "ignored.txt"), source_root=source_root)
        is False
    )
    assert (
        path_filter.allows(_entry(source_root, "kept.txt"), source_root=source_root)
        is True
    )


def test_ignore_line_with_leading_space_hash_is_not_comment(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text(" #literal-hash.txt\n", encoding="utf-8")

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)

    assert (
        path_filter.allows(
            _entry(source_root, " #literal-hash.txt"), source_root=source_root
        )
        is False
    )


def test_ignore_file_blank_whitespace_only_line_is_ignored(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text("   \n\t\nignored.txt\n", encoding="utf-8")

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)

    assert (
        path_filter.allows(_entry(source_root, "ignored.txt"), source_root=source_root)
        is False
    )


def test_gitignore_allows_with_relative_source_root_and_absolute_entry_path(
    tmp_path: Path, monkeypatch
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=Path("source"))

    assert (
        path_filter.allows(
            FileEntry(
                path=(source_root / "ignored.txt"),
                relative_path=Path("ignored.txt"),
                size=0,
                mtime=0.0,
                is_directory=False,
            ),
            source_root=Path("source"),
        )
        is False
    )


def test_gitignore_can_prune_subtree_without_matching_negation(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text("build/\n", encoding="utf-8")
    build_dir = source_root / "build"
    build_dir.mkdir()

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)
    build_entry = _entry(source_root, "build", is_directory=True)

    assert path_filter.allows(build_entry, source_root=source_root) is False
    assert path_filter.can_prune_subtree(build_entry, source_root=source_root) is True


def test_gitignore_does_not_prune_when_negation_may_reinclude_descendant(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / ".gitignore").write_text(
        "build/\n!build/keep.txt\n", encoding="utf-8"
    )
    build_dir = source_root / "build"
    build_dir.mkdir()

    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)
    build_entry = _entry(source_root, "build", is_directory=True)

    assert path_filter.allows(build_entry, source_root=source_root) is False
    assert path_filter.can_prune_subtree(build_entry, source_root=source_root) is False


def test_ignore_match_resolution_labels_user_layer(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    path_filter = GitIgnorePathFilter(user_patterns=("skip.txt",))
    path_filter.prepare_walk_directory(source_root, source_root=source_root)
    entry = _entry(source_root, "skip.txt")
    assert path_filter.ignore_match_resolution(entry, source_root=source_root) == (
        IgnoreMatchResolution(is_ignored=True, source_label="user")
    )


def test_ignore_match_resolution_labels_ignore_file_relative_to_source_root(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    nested = source_root / "nested"
    nested.mkdir(parents=True)
    (nested / ".gitignore").write_text("inner.txt\n", encoding="utf-8")
    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(nested, source_root=source_root)
    entry = _entry(source_root, "nested/inner.txt")
    assert path_filter.ignore_match_resolution(entry, source_root=source_root) == (
        IgnoreMatchResolution(is_ignored=True, source_label="nested/.gitignore")
    )


def test_ignore_match_resolution_no_match_has_no_source_label(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    path_filter = GitIgnorePathFilter()
    path_filter.prepare_walk_directory(source_root, source_root=source_root)
    entry = _entry(source_root, "present.txt")
    assert path_filter.ignore_match_resolution(entry, source_root=source_root) == (
        IgnoreMatchResolution(is_ignored=False, source_label=None)
    )
