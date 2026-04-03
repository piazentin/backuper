"""Unit tests for `run_restore_flow`."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from backuper.implementation.commands import RestoreCommand
from backuper.implementation.controllers.restore import run_restore_flow
from backuper.implementation.interfaces import FileEntry


@pytest.mark.asyncio
async def test_run_restore_flow_raises_when_version_missing(tmp_path: Path) -> None:
    class FakeDb:
        async def get_version_by_name(self, name: str) -> str:
            raise RuntimeError("missing")

    class FakeFileStore:
        def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
            raise AssertionError("unreachable")

    with pytest.raises(
        ValueError, match="Backup version missing_version does not exist in source"
    ):
        await run_restore_flow(
            RestoreCommand(
                location=str(tmp_path),
                destination=str(tmp_path / "out"),
                version_name="missing_version",
            ),
            db=FakeDb(),
            filestore=FakeFileStore(),
        )


@pytest.mark.asyncio
async def test_run_restore_flow_raises_when_file_hash_missing(tmp_path: Path) -> None:
    class FakeDb:
        async def get_version_by_name(self, name: str) -> str:
            return "v1"

        async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
            yield FileEntry(
                path=Path("a.txt"),
                relative_path=Path("a.txt"),
                size=1,
                mtime=0.0,
                is_directory=False,
                hash=None,
                is_compressed=False,
            )

    class FakeFileStore:
        def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
            raise AssertionError("unreachable")

    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="Missing hash for restore entry"):
        await run_restore_flow(
            RestoreCommand(
                location=str(tmp_path),
                destination=str(dest),
                version_name="v1",
            ),
            db=FakeDb(),
            filestore=FakeFileStore(),
        )


@pytest.mark.asyncio
async def test_run_restore_flow_writes_file_and_makes_dirs(tmp_path: Path) -> None:
    class FakeDb:
        async def get_version_by_name(self, name: str) -> str:
            return "v1"

        async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
            yield FileEntry(
                path=Path("sub") / "a.txt",
                relative_path=Path("sub") / "a.txt",
                size=3,
                mtime=0.0,
                is_directory=False,
                hash="deadbeef",
                is_compressed=False,
            )

    class FakeFileStore:
        def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
            assert file_hash == "deadbeef"
            assert is_compressed is False
            return b"hey"

    dest = tmp_path / "out"
    await run_restore_flow(
        RestoreCommand(
            location=str(tmp_path),
            destination=str(dest),
            version_name="v1",
        ),
        db=FakeDb(),
        filestore=FakeFileStore(),
    )
    assert (dest / "sub" / "a.txt").read_bytes() == b"hey"


@pytest.mark.asyncio
async def test_run_restore_flow_invokes_on_restore_file(tmp_path: Path) -> None:
    class FakeDb:
        async def get_version_by_name(self, name: str) -> str:
            return "v1"

        async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
            yield FileEntry(
                path=Path("a.txt"),
                relative_path=Path("a.txt"),
                size=1,
                mtime=0.0,
                is_directory=False,
                hash="h1",
                is_compressed=False,
            )

    class FakeFileStore:
        def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
            return b"x"

    seen: list[Path] = []

    dest = tmp_path / "out"
    await run_restore_flow(
        RestoreCommand(
            location=str(tmp_path),
            destination=str(dest),
            version_name="v1",
        ),
        db=FakeDb(),
        filestore=FakeFileStore(),
        on_restore_file=lambda p: seen.append(p),
    )
    assert seen == [Path("a.txt")]


@pytest.mark.asyncio
async def test_run_restore_flow_rejects_path_outside_destination(
    tmp_path: Path,
) -> None:
    class FakeDb:
        async def get_version_by_name(self, name: str) -> str:
            return "v1"

        async def list_files(self, version: str) -> AsyncIterator[FileEntry]:
            yield FileEntry(
                path=Path("x.txt"),
                relative_path=Path("..") / "outside.txt",
                size=1,
                mtime=0.0,
                is_directory=False,
                hash="h1",
                is_compressed=False,
            )

    class FakeFileStore:
        def read_blob(self, file_hash: str, is_compressed: bool) -> bytes:
            return b"x"

    dest = tmp_path / "out"
    dest.mkdir()
    with pytest.raises(ValueError, match="outside destination"):
        await run_restore_flow(
            RestoreCommand(
                location=str(tmp_path),
                destination=str(dest),
                version_name="v1",
            ),
            db=FakeDb(),
            filestore=FakeFileStore(),
        )
