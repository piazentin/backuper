from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pathspec.patterns.gitignore import GitIgnorePatternError
from pathspec.patterns.gitwildmatch import GitIgnoreSpecPattern

from backuper.models import CliUsageError
from backuper.utils.gitignore_lines import iter_gitignore_pattern_lines


def build_user_ignore_patterns(
    *,
    ignore_patterns: tuple[str, ...],
    ignore_files: tuple[str, ...],
) -> tuple[str, ...]:
    """Merge ``--ignore-pattern`` / ``--ignore-file`` into one user layer.

    Order: every pattern flag in argv order, then each ignore file in argv order
    (non-blank, non-``#`` comment lines per :func:`~backuper.utils.gitignore_lines.iter_gitignore_pattern_lines`).
    Relative ``--ignore-file`` paths use the process working directory.

    Raises:
        CliUsageError: Missing or non-file ignore path, or a pattern line that
            does not compile (after the same line filtering as on-disk ignore files).
    """
    merged: list[str] = []
    for raw_argv in ignore_patterns:
        merged.extend(_pattern_lines_from_source([raw_argv], source="--ignore-pattern"))
    for file_path in ignore_files:
        path = Path(file_path)
        if not path.is_file():
            raise CliUsageError(
                f'ignore file "{file_path}" is missing or not a regular file'
            )
        text = path.read_text(encoding="utf-8-sig")
        merged.extend(
            _pattern_lines_from_source(
                text.splitlines(),
                source=f'ignore file "{file_path}"',
            )
        )
    return tuple(merged)


def _pattern_lines_from_source(
    lines: Sequence[str],
    *,
    source: str,
) -> list[str]:
    """Same filtering and compilation rules as :func:`backuper.components.path_ignore._compile_patterns`."""
    kept: list[str] = []
    for raw_line in iter_gitignore_pattern_lines(lines):
        try:
            compiled = GitIgnoreSpecPattern(raw_line)
        except GitIgnorePatternError as exc:
            raise CliUsageError(
                f"invalid ignore pattern {raw_line!r} ({source})"
            ) from exc
        if compiled.include is not None:
            kept.append(raw_line)
    return kept
