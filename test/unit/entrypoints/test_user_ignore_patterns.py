from __future__ import annotations

from pathlib import Path

import pytest
from backuper.entrypoints.cli.user_ignore_patterns import build_user_ignore_patterns
from backuper.models import CliUsageError


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
