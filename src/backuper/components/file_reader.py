import logging
import os
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from backuper.models import FileEntry
from backuper.ports import FileReader, PathFilter

from .path_ignore import GitIgnorePathFilter


@dataclass
class WalkMetrics:
    visited_directories: int
    visited_files: int
    skipped_entries: int
    pruned_directories: int

    @property
    def visited_entries(self) -> int:
        return self.visited_directories + self.visited_files


class LocalFileReader(FileReader):
    def __init__(
        self,
        path_filter: PathFilter | None = None,
        *,
        collect_walk_metrics: bool = False,
    ) -> None:
        self._path_filter = path_filter or GitIgnorePathFilter()
        self._logger = logging.getLogger(__name__)
        self._collect_walk_metrics = collect_walk_metrics
        self._last_walk_metrics: WalkMetrics | None = None

    async def read_directory(self, path: Path) -> AsyncGenerator[FileEntry, None]:
        metrics = self._new_metrics()
        normalized_source_root = path.absolute()
        for root, dirs, files in os.walk(path, followlinks=False):
            root_path = Path(root)
            normalized_walk_root = root_path.absolute()
            self._path_filter.prepare_walk_directory(
                normalized_walk_root, source_root=normalized_source_root
            )
            self._increment_metric(metrics, "visited_directories")
            walkable_dirs: list[str] = []
            for dir_name in dirs:
                dir_entry = self._build_directory_entry(
                    normalized_source_root=normalized_source_root,
                    root_path=root_path,
                    dir_name=dir_name,
                )
                skip_reason = self._path_filter.exclusion_reason(
                    dir_entry, source_root=normalized_source_root
                )
                should_yield = skip_reason is None
                should_prune = False
                if skip_reason is not None:
                    self._logger.info(
                        "Skipping %s (%s)",
                        dir_entry.relative_path,
                        skip_reason,
                    )
                    self._increment_metric(metrics, "skipped_entries")
                    should_prune = self._path_filter.can_prune_subtree(
                        dir_entry, source_root=normalized_source_root
                    )
                    if should_prune:
                        self._increment_metric(metrics, "pruned_directories")
                if not should_prune:
                    walkable_dirs.append(dir_name)
                if should_yield:
                    yield dir_entry

            dirs[:] = walkable_dirs

            for file in files:
                self._increment_metric(metrics, "visited_files")
                file_entry = self._build_file_entry(
                    normalized_source_root=normalized_source_root,
                    root_path=root_path,
                    file_name=file,
                )
                file_skip_reason = self._path_filter.exclusion_reason(
                    file_entry, source_root=normalized_source_root
                )
                if file_skip_reason is not None:
                    self._logger.info(
                        "Skipping %s (%s)",
                        file_entry.relative_path,
                        file_skip_reason,
                    )
                    self._increment_metric(metrics, "skipped_entries")
                    continue
                yield file_entry
        self._last_walk_metrics = metrics

    def _build_directory_entry(
        self,
        *,
        normalized_source_root: Path,
        root_path: Path,
        dir_name: str,
    ) -> FileEntry:
        dir_path = root_path / dir_name
        return FileEntry(
            path=dir_path,
            relative_path=self._relative_to_source_root(
                entry_path=dir_path, normalized_source_root=normalized_source_root
            ),
            size=0,
            mtime=os.path.getmtime(dir_path),
            is_directory=True,
        )

    def _build_file_entry(
        self,
        *,
        normalized_source_root: Path,
        root_path: Path,
        file_name: str,
    ) -> FileEntry:
        file_path = root_path / file_name
        return FileEntry(
            path=file_path,
            relative_path=self._relative_to_source_root(
                entry_path=file_path, normalized_source_root=normalized_source_root
            ),
            size=os.path.getsize(file_path),
            mtime=os.path.getmtime(file_path),
            is_directory=False,
        )

    def _relative_to_source_root(
        self, *, entry_path: Path, normalized_source_root: Path
    ) -> Path:
        normalized_entry_path = entry_path.absolute()
        return normalized_entry_path.relative_to(normalized_source_root)

    def get_last_walk_metrics(self) -> WalkMetrics | None:
        return self._last_walk_metrics

    def _new_metrics(self) -> WalkMetrics | None:
        if not self._collect_walk_metrics:
            return None
        return WalkMetrics(
            visited_directories=0,
            visited_files=0,
            skipped_entries=0,
            pruned_directories=0,
        )

    def _increment_metric(
        self,
        metrics: WalkMetrics | None,
        field_name: str,
    ) -> None:
        if metrics is None:
            return
        setattr(metrics, field_name, getattr(metrics, field_name) + 1)
