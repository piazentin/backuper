import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from backuper.models import FileEntry
from backuper.ports import FileReader, PathFilter

from .path_ignore import GitIgnorePathFilter


class LocalFileReader(FileReader):
    def __init__(self, path_filter: PathFilter | None = None) -> None:
        self._path_filter = path_filter or GitIgnorePathFilter()
        self._logger = logging.getLogger(__name__)

    async def read_directory(self, path: Path) -> AsyncGenerator[FileEntry, None]:
        normalized_source_root = path.absolute()
        for root, dirs, files in os.walk(path, followlinks=False):
            root_path = Path(root)
            normalized_walk_root = root_path.absolute()
            self._path_filter.prepare_walk_directory(
                normalized_walk_root, source_root=normalized_source_root
            )
            walkable_dirs: list[str] = []
            for dir_name in dirs:
                dir_entry = self._build_directory_entry(
                    normalized_source_root=normalized_source_root,
                    root_path=root_path,
                    dir_name=dir_name,
                )
                should_yield = self._path_filter.allows(
                    dir_entry, source_root=normalized_source_root
                )
                should_prune = False
                if not should_yield:
                    self._logger.info(
                        "Skipping %s (%s)",
                        dir_entry.relative_path,
                        self._skip_reason(),
                    )
                    should_prune = self._path_filter.can_prune_subtree(
                        dir_entry, source_root=normalized_source_root
                    )
                if not should_prune:
                    walkable_dirs.append(dir_name)
                if should_yield:
                    yield dir_entry

            dirs[:] = walkable_dirs

            for file in files:
                file_entry = self._build_file_entry(
                    normalized_source_root=normalized_source_root,
                    root_path=root_path,
                    file_name=file,
                )
                if not self._path_filter.allows(
                    file_entry, source_root=normalized_source_root
                ):
                    self._logger.info(
                        "Skipping %s (%s)",
                        file_entry.relative_path,
                        self._skip_reason(),
                    )
                    continue
                yield file_entry

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

    def _skip_reason(self) -> str:
        return f"excluded by {self._path_filter.__class__.__name__}"
