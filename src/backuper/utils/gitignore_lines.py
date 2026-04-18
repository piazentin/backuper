from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence


def iter_gitignore_pattern_lines(lines: Iterable[str]) -> Iterator[str]:
    """Yield non-blank, non-comment lines before pathspec compilation.

    Matches tree ignore files (``.gitignore`` / ``.backupignore``):

    - Blank lines (whitespace-only) are dropped.
    - Lines whose first character is ``#`` are comments; a leading space means the
      line is *not* treated as a comment (e.g. a pattern matching a literal ``#``).
    """
    for raw_line in lines:
        if raw_line.strip() == "":
            continue
        if raw_line.startswith("#"):
            continue
        yield raw_line


def gitignore_pattern_lines(lines: Sequence[str]) -> tuple[str, ...]:
    """Return pattern lines from an already-split line sequence (same rules as :func:`iter_gitignore_pattern_lines`)."""
    return tuple(iter_gitignore_pattern_lines(lines))


def gitignore_pattern_lines_from_text(text: str) -> tuple[str, ...]:
    """Return pattern lines from full-file text.

    If ``text`` still begins with a UTF-8 BOM (U+FEFF), it is stripped so the first
    logical line matches ``Path.read_text(encoding="utf-8-sig")`` behavior.
    Line breaks use :meth:`str.splitlines` (``\\r\\n``, ``\\r``, ``\\n``).
    """
    if text.startswith("\ufeff"):
        text = text.removeprefix("\ufeff")
    return gitignore_pattern_lines(text.splitlines())
