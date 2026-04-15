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
        for root, dirs, files in os.walk(path, followlinks=False):
            root_path = Path(root)
            self._path_filter.prepare_walk_directory(root_path, source_root=path)
            pruned_dir_names: set[str] = set()

            retained_dirs: list[str] = []
            for dir_name in dirs:
                dir_entry = self._build_directory_entry(
                    source_root=path, root_path=root_path, dir_name=dir_name
                )
                if not self._path_filter.allows(dir_entry, source_root=path):
                    self._logger.info(
                        "Skipping %s (%s)",
                        dir_entry.relative_path,
                        self._skip_reason(),
                    )
                    if self._path_filter.can_prune_subtree(dir_entry, source_root=path):
                        pruned_dir_names.add(dir_name)
                    continue
                retained_dirs.append(dir_name)
                yield dir_entry

            if pruned_dir_names:
                dirs[:] = [
                    name for name in retained_dirs if name not in pruned_dir_names
                ]
            else:
                dirs[:] = retained_dirs

            for file in files:
                file_entry = self._build_file_entry(
                    source_root=path, root_path=root_path, file_name=file
                )
                if not self._path_filter.allows(file_entry, source_root=path):
                    self._logger.info(
                        "Skipping %s (%s)",
                        file_entry.relative_path,
                        self._skip_reason(),
                    )
                    continue
                yield file_entry

    def _build_directory_entry(
        self, *, source_root: Path, root_path: Path, dir_name: str
    ) -> FileEntry:
        dir_path = root_path / dir_name
        return FileEntry(
            path=dir_path,
            relative_path=dir_path.relative_to(source_root),
            size=0,
            mtime=os.path.getmtime(dir_path),
            is_directory=True,
        )

    def _build_file_entry(
        self, *, source_root: Path, root_path: Path, file_name: str
    ) -> FileEntry:
        file_path = root_path / file_name
        return FileEntry(
            path=file_path,
            relative_path=file_path.relative_to(source_root),
            size=os.path.getsize(file_path),
            mtime=os.path.getmtime(file_path),
            is_directory=False,
        )

    def _skip_reason(self) -> str:
        return f"excluded by {self._path_filter.__class__.__name__}"
