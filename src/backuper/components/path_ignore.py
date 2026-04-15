from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pathspec.patterns.gitwildmatch import GitIgnoreSpecPattern

from backuper.models import FileEntry
from backuper.ports import PathFilter

IGNORE_FILE_NAMES: tuple[str, str] = (".backupignore", ".gitignore")


@dataclass(frozen=True)
class _PatternLayer:
    patterns: tuple[GitIgnoreSpecPattern, ...]


class NullPathFilter(PathFilter):
    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        return None

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return True


class GitIgnorePathFilter(PathFilter):
    def __init__(
        self,
        *,
        user_patterns: Sequence[str] = (),
        ignore_file_names: Sequence[str] = IGNORE_FILE_NAMES,
    ) -> None:
        self._user_layer = _PatternLayer(patterns=_compile_patterns(user_patterns))
        self._ignore_file_names = tuple(sorted(ignore_file_names))
        self._directory_layers: dict[Path, tuple[_PatternLayer, ...]] = {}
        self._ignore_file_pattern_cache: dict[
            Path, tuple[GitIgnoreSpecPattern, ...]
        ] = {}

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        self._layers_for_directory(walk_root, source_root=source_root)

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        parent = entry.path.parent
        layers = self._layers_for_directory(parent, source_root=source_root)
        entry_relative_path = entry.path.relative_to(source_root)
        is_ignored = _resolve_last_match(
            relative_path=entry_relative_path,
            is_directory=entry.is_directory,
            layers=layers,
            source_root=source_root,
        )
        return not is_ignored

    def _layers_for_directory(
        self, walk_directory: Path, *, source_root: Path
    ) -> tuple[_PatternLayer, ...]:
        """Build effective pattern layers for a walk directory.

        Layer order is lowest to highest precedence:
        user patterns, then ignore files discovered from source root down to the
        walk directory (per-anchor filename order). The resulting tuple is cached.
        """
        if walk_directory in self._directory_layers:
            return self._directory_layers[walk_directory]

        anchor_chain = _anchor_chain(
            source_root=source_root, walk_directory=walk_directory
        )
        layers: list[_PatternLayer] = [self._user_layer]
        for anchor in anchor_chain:
            for ignore_file_name in self._ignore_file_names:
                ignore_file = anchor / ignore_file_name
                patterns = self._patterns_for_ignore_file(ignore_file)
                if patterns:
                    layers.append(_PatternLayer(patterns=patterns))
        built = tuple(layers)
        self._directory_layers[walk_directory] = built
        return built

    def _patterns_for_ignore_file(
        self, ignore_file: Path
    ) -> tuple[GitIgnoreSpecPattern, ...]:
        if ignore_file in self._ignore_file_pattern_cache:
            return self._ignore_file_pattern_cache[ignore_file]

        if not ignore_file.is_file():
            patterns: tuple[GitIgnoreSpecPattern, ...] = ()
        else:
            lines = ignore_file.read_text(encoding="utf-8-sig").splitlines()
            patterns = _compile_patterns(lines)

        self._ignore_file_pattern_cache[ignore_file] = patterns
        return patterns


def _anchor_chain(*, source_root: Path, walk_directory: Path) -> tuple[Path, ...]:
    """Return root-to-leaf anchors that can contribute ignore files."""
    relative = walk_directory.relative_to(source_root)
    anchors = [source_root]
    current = source_root
    for segment in relative.parts:
        current = current / segment
        anchors.append(current)
    return tuple(anchors)


def _compile_patterns(lines: Sequence[str]) -> tuple[GitIgnoreSpecPattern, ...]:
    patterns: list[GitIgnoreSpecPattern] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        compiled = GitIgnoreSpecPattern(raw_line)
        if compiled.include is not None:
            patterns.append(compiled)
    return tuple(patterns)


def _resolve_last_match(
    *,
    relative_path: Path,
    is_directory: bool,
    layers: tuple[_PatternLayer, ...],
    source_root: Path,
) -> bool:
    """Evaluate gitignore semantics where the final matching rule decides."""
    ignored: bool | None = None
    for layer in layers:
        for pattern in layer.patterns:
            if _pattern_matches_path(
                pattern=pattern,
                relative_path=relative_path,
                is_directory=is_directory,
                source_root=source_root,
            ):
                ignored = bool(pattern.include)
    return bool(ignored)


def _pattern_matches_path(
    *,
    pattern: GitIgnoreSpecPattern,
    relative_path: Path,
    is_directory: bool,
    source_root: Path,
) -> bool:
    """Match a relative path; directories also try a trailing-slash variant."""
    relative_posix_path = relative_path.as_posix()
    if source_root == Path("."):
        relative_posix_path = relative_posix_path.removeprefix("./")
    if pattern.match_file(relative_posix_path):
        return True
    if is_directory:
        return pattern.match_file(f"{relative_posix_path}/")
    return False
