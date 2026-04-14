from pathlib import Path

from backuper.components.path_ignore import GitIgnorePathFilter
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
