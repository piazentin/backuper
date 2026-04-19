from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pathspec.patterns.gitwildmatch import GitIgnoreSpecPattern

from backuper.models import FileEntry
from backuper.ports import PathFilter
from backuper.utils.gitignore_lines import iter_gitignore_pattern_lines

IGNORE_FILE_NAMES: tuple[str, str] = (".backupignore", ".gitignore")

_USER_LAYER_LABEL = "user"


@dataclass(frozen=True)
class IgnoreMatchResolution:
    """Outcome of last-match gitignore evaluation for a path under ``source_root``."""

    is_ignored: bool
    """True when the path is excluded after applying all layers."""
    source_label: str | None
    """Layer that owned the winning pattern: ``\"user\"`` for CLI patterns, else a POSIX
    path relative to the backup source root (e.g. ``\".gitignore\"``, ``\"pkg/.backupignore\"``).
    ``None`` when no pattern matched.
    """


@dataclass(frozen=True)
class _PatternLayer:
    patterns: tuple[GitIgnoreSpecPattern, ...]
    label: str


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
        self._user_layer = _PatternLayer(
            patterns=_compile_patterns(user_patterns),
            label=_USER_LAYER_LABEL,
        )
        self._ignore_file_names = tuple(sorted(ignore_file_names))
        self._directory_layers: dict[Path, tuple[_PatternLayer, ...]] = {}
        self._ignore_file_pattern_cache: dict[
            Path, tuple[GitIgnoreSpecPattern, ...]
        ] = {}

    def prepare_walk_directory(self, walk_root: Path, *, source_root: Path) -> None:
        normalized_source_root = _normalize_path(source_root)
        normalized_walk_root = _normalize_path(walk_root)
        self._layers_for_directory(
            normalized_walk_root, source_root=normalized_source_root
        )

    def ignore_match_resolution(
        self, entry: FileEntry, *, source_root: Path
    ) -> IgnoreMatchResolution:
        normalized_source_root = _normalize_path(source_root)
        normalized_entry_path = _normalize_path(entry.path)
        parent = normalized_entry_path.parent
        layers = self._layers_for_directory(parent, source_root=normalized_source_root)
        entry_relative_path = _entry_relative_path(
            entry=entry,
            normalized_entry_path=normalized_entry_path,
            normalized_source_root=normalized_source_root,
        )
        return _resolve_last_match(
            relative_path=entry_relative_path,
            is_directory=entry.is_directory,
            layers=layers,
            source_root=normalized_source_root,
        )

    def allows(self, entry: FileEntry, *, source_root: Path) -> bool:
        return not self.ignore_match_resolution(
            entry, source_root=source_root
        ).is_ignored

    def can_prune_subtree(self, entry: FileEntry, *, source_root: Path) -> bool:
        if not entry.is_directory:
            return False

        normalized_source_root = _normalize_path(source_root)
        normalized_entry_path = _normalize_path(entry.path)
        parent_layers = self._layers_for_directory(
            normalized_entry_path.parent, source_root=normalized_source_root
        )
        entry_relative_path = _entry_relative_path(
            entry=entry,
            normalized_entry_path=normalized_entry_path,
            normalized_source_root=normalized_source_root,
        )
        if not _resolve_last_match(
            relative_path=entry_relative_path,
            is_directory=True,
            layers=parent_layers,
            source_root=normalized_source_root,
        ).is_ignored:
            return False
        if _layers_may_reinclude_descendant(
            layers=parent_layers,
            directory_relative_path=entry_relative_path,
            source_root=normalized_source_root,
        ):
            return False
        return True

    def _layers_for_directory(
        self, walk_directory: Path, *, source_root: Path
    ) -> tuple[_PatternLayer, ...]:
        """Build effective pattern layers for a walk directory.

        Layer order is lowest to highest precedence:
        user patterns, then ignore files discovered from source root down to the
        walk directory (per-anchor filename order). The resulting tuple is cached.
        """
        normalized_source_root = _normalize_path(source_root)
        normalized_walk_directory = _normalize_path(walk_directory)

        if normalized_walk_directory in self._directory_layers:
            return self._directory_layers[normalized_walk_directory]

        anchor_chain = _anchor_chain(
            source_root=normalized_source_root, walk_directory=normalized_walk_directory
        )
        layers: list[_PatternLayer] = [self._user_layer]
        for anchor in anchor_chain:
            for ignore_file_name in self._ignore_file_names:
                ignore_file = anchor / ignore_file_name
                patterns = self._patterns_for_ignore_file(ignore_file)
                if patterns:
                    rel_label = ignore_file.relative_to(
                        normalized_source_root
                    ).as_posix()
                    layers.append(_PatternLayer(patterns=patterns, label=rel_label))
        built = tuple(layers)
        self._directory_layers[normalized_walk_directory] = built
        return built

    def _patterns_for_ignore_file(
        self, ignore_file: Path
    ) -> tuple[GitIgnoreSpecPattern, ...]:
        if ignore_file in self._ignore_file_pattern_cache:
            return self._ignore_file_pattern_cache[ignore_file]

        if not ignore_file.is_file():
            patterns: tuple[GitIgnoreSpecPattern, ...] = ()
        else:
            text = ignore_file.read_text(encoding="utf-8-sig")
            patterns = _compile_patterns(text.splitlines())

        self._ignore_file_pattern_cache[ignore_file] = patterns
        return patterns


def _anchor_chain(*, source_root: Path, walk_directory: Path) -> tuple[Path, ...]:
    """Return root-to-leaf anchors that can contribute ignore files."""
    normalized_source_root = _normalize_path(source_root)
    normalized_walk_directory = _normalize_path(walk_directory)
    relative = normalized_walk_directory.relative_to(normalized_source_root)
    anchors = [normalized_source_root]
    current = normalized_source_root
    for segment in relative.parts:
        current = current / segment
        anchors.append(current)
    return tuple(anchors)


def _normalize_path(path: Path) -> Path:
    return path.absolute()


def _entry_relative_path(
    *,
    entry: FileEntry,
    normalized_entry_path: Path,
    normalized_source_root: Path,
) -> Path:
    if not entry.relative_path.is_absolute():
        return entry.relative_path
    return normalized_entry_path.relative_to(normalized_source_root)


def _compile_patterns(lines: Sequence[str]) -> tuple[GitIgnoreSpecPattern, ...]:
    patterns: list[GitIgnoreSpecPattern] = []
    for raw_line in iter_gitignore_pattern_lines(lines):
        compiled = GitIgnoreSpecPattern(raw_line)
        if compiled.include is not None:
            patterns.append(compiled)
    return tuple(patterns)


def _layers_may_reinclude_descendant(
    *,
    layers: tuple[_PatternLayer, ...],
    directory_relative_path: Path,
    source_root: Path,
) -> bool:
    """Conservatively detect whether descendants might be re-included."""
    for layer in layers:
        for pattern in layer.patterns:
            if pattern.include is not False:
                continue
            if _negation_pattern_may_match_descendant(
                pattern=pattern,
                directory_relative_path=directory_relative_path,
                source_root=source_root,
            ):
                return True
    return False


def _negation_pattern_may_match_descendant(
    *,
    pattern: GitIgnoreSpecPattern,
    directory_relative_path: Path,
    source_root: Path,
) -> bool:
    pattern_text = getattr(pattern, "pattern", "")
    if not isinstance(pattern_text, str):
        return True

    if _negation_text_targets_subtree(
        pattern_text=pattern_text,
        directory_relative_path=directory_relative_path,
    ):
        return True

    candidate_bases = _candidate_descendant_match_bases(directory_relative_path)
    for base in candidate_bases:
        if _pattern_matches_path(
            pattern=pattern,
            relative_path=base,
            is_directory=False,
            source_root=source_root,
        ):
            return True
    return False


def _negation_text_targets_subtree(
    *, pattern_text: str, directory_relative_path: Path
) -> bool:
    """Conservative textual pre-check before pattern probes."""
    normalized_pattern = pattern_text.removeprefix("!").strip()
    if normalized_pattern.startswith("\\!"):
        normalized_pattern = normalized_pattern[1:]
    normalized_pattern = normalized_pattern.lstrip("/")
    directory_posix = directory_relative_path.as_posix().strip("/")

    if normalized_pattern in {"", "."}:
        return False
    if directory_posix in {"", "."}:
        return True
    if normalized_pattern.startswith(f"{directory_posix}/"):
        return True
    if "/" not in normalized_pattern:
        return True
    if any(token in normalized_pattern for token in ("**", "*", "?")):
        return True
    return False


def _candidate_descendant_match_bases(
    directory_relative_path: Path,
) -> tuple[Path, ...]:
    posix = directory_relative_path.as_posix().strip("/")
    if posix in {"", "."}:
        return (Path("x"), Path("x/y"))
    return (Path(f"{posix}/x"), Path(f"{posix}/x/y"))


def _resolve_last_match(
    *,
    relative_path: Path,
    is_directory: bool,
    layers: tuple[_PatternLayer, ...],
    source_root: Path,
) -> IgnoreMatchResolution:
    """Evaluate gitignore semantics where the final matching rule decides."""
    ignored: bool | None = None
    winning_label: str | None = None
    for layer in layers:
        for pattern in layer.patterns:
            if _pattern_matches_path(
                pattern=pattern,
                relative_path=relative_path,
                is_directory=is_directory,
                source_root=source_root,
            ):
                ignored = bool(pattern.include)
                winning_label = layer.label
    if ignored is None:
        return IgnoreMatchResolution(is_ignored=False, source_label=None)
    return IgnoreMatchResolution(is_ignored=bool(ignored), source_label=winning_label)


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
