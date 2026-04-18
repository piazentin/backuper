from __future__ import annotations

from pathlib import Path

import pytest
from backuper.components.path_ignore import GitIgnorePathFilter
from backuper.entrypoints.cli.user_ignore_patterns import build_user_ignore_patterns
from backuper.models import CliUsageError, FileEntry


def _entry(source_root: Path, relative_path: str) -> FileEntry:
    return FileEntry(
        path=source_root / relative_path,
        relative_path=Path(relative_path),
        size=0,
        mtime=0.0,
        is_directory=False,
    )


def _allows_with_user_patterns(
    source_root: Path, relative_path: str, *, user_patterns: tuple[str, ...]
) -> bool:
    filt = GitIgnorePathFilter(user_patterns=user_patterns)
    filt.prepare_walk_directory(source_root, source_root=source_root)
    return filt.allows(_entry(source_root, relative_path), source_root=source_root)


def test_build_user_ignore_patterns_empty() -> None:
    assert build_user_ignore_patterns(ignore_patterns=(), ignore_files=()) == ()


def test_build_user_ignore_patterns_argv_order_then_files(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.ignore"
    first.write_text("from_a\n", encoding="utf-8")
    second = tmp_path / "b.ignore"
    second.write_text("from_b\n", encoding="utf-8")
    assert build_user_ignore_patterns(
        ignore_patterns=("p1", "p2"),
        ignore_files=(str(first), str(second)),
    ) == ("p1", "p2", "from_a", "from_b")


def test_build_user_ignore_patterns_interleaved_file_order(
    tmp_path: Path,
) -> None:
    f1 = tmp_path / "one"
    f1.write_text("a\n", encoding="utf-8")
    f2 = tmp_path / "two"
    f2.write_text("b\n", encoding="utf-8")
    assert build_user_ignore_patterns(
        ignore_patterns=("mid",),
        ignore_files=(str(f1), str(f2)),
    ) == ("mid", "a", "b")


def test_build_user_ignore_patterns_skips_comments_and_blank_in_file(
    tmp_path: Path,
) -> None:
    f = tmp_path / "x.ignore"
    f.write_text("\n# c\n\nkeep\n", encoding="utf-8")
    assert build_user_ignore_patterns(
        ignore_patterns=("# inline\n", "z"),
        ignore_files=(str(f),),
    ) == ("z", "keep")


def test_build_user_ignore_patterns_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.ignore"
    with pytest.raises(
        CliUsageError,
        match=r'ignore file ".*nope\.ignore" is missing or not a regular file',
    ):
        build_user_ignore_patterns(ignore_patterns=(), ignore_files=(str(missing),))


def test_build_user_ignore_patterns_rejects_directory(tmp_path: Path) -> None:
    d = tmp_path / "dir"
    d.mkdir()
    with pytest.raises(CliUsageError, match="not a regular file"):
        build_user_ignore_patterns(ignore_patterns=(), ignore_files=(str(d),))


def test_build_user_ignore_patterns_invalid_line_in_file(
    tmp_path: Path,
) -> None:
    f = tmp_path / "bad.ignore"
    f.write_text("ok\na\\\n", encoding="utf-8")
    with pytest.raises(CliUsageError, match=r"invalid ignore pattern .*ignore file"):
        build_user_ignore_patterns(ignore_patterns=(), ignore_files=(str(f),))


def test_build_user_ignore_patterns_invalid_argv_pattern() -> None:
    with pytest.raises(
        CliUsageError, match=r"invalid ignore pattern .*--ignore-pattern"
    ):
        build_user_ignore_patterns(ignore_patterns=("a\\",), ignore_files=())


def test_user_ignore_merge_order_two_files_last_match_wins(
    tmp_path: Path,
) -> None:
    """P3.3: ``--ignore-file`` order is stable and affects effective matching."""
    source_root = tmp_path / "source"
    source_root.mkdir()
    ignore_first = tmp_path / "first.ignore"
    ignore_first.write_text("blocked.txt\n", encoding="utf-8")
    unignore_second = tmp_path / "second.ignore"
    unignore_second.write_text("!blocked.txt\n", encoding="utf-8")
    merged_keep = build_user_ignore_patterns(
        ignore_patterns=(),
        ignore_files=(str(ignore_first), str(unignore_second)),
    )
    assert (
        _allows_with_user_patterns(
            source_root, "blocked.txt", user_patterns=merged_keep
        )
        is True
    )

    unignore_first = tmp_path / "a_unignore.ignore"
    unignore_first.write_text("!blocked.txt\n", encoding="utf-8")
    ignore_second = tmp_path / "b_block.ignore"
    ignore_second.write_text("blocked.txt\n", encoding="utf-8")
    merged_drop = build_user_ignore_patterns(
        ignore_patterns=(),
        ignore_files=(str(unignore_first), str(ignore_second)),
    )
    assert (
        _allows_with_user_patterns(
            source_root, "blocked.txt", user_patterns=merged_drop
        )
        is False
    )


def test_user_ignore_merge_order_argv_patterns_then_files_p33(
    tmp_path: Path,
) -> None:
    """P3.3: argv ``--ignore-pattern`` lines precede all ``--ignore-file`` lines."""
    source_root = tmp_path / "source"
    source_root.mkdir()
    extra = tmp_path / "extra.ignore"
    extra.write_text("!special.txt\n", encoding="utf-8")
    merged = build_user_ignore_patterns(
        ignore_patterns=("*.txt",),
        ignore_files=(str(extra),),
    )
    assert merged == ("*.txt", "!special.txt")
    assert (
        _allows_with_user_patterns(source_root, "special.txt", user_patterns=merged)
        is True
    )

    reversed_merge = ("!special.txt", "*.txt")
    assert (
        _allows_with_user_patterns(
            source_root, "special.txt", user_patterns=reversed_merge
        )
        is False
    )
