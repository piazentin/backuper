"""Unit tests for ``scripts.migrate_version_csv.blob_meta`` ZIP size/mtime enrichment."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile

from scripts.migrate_version_csv.blob_meta import (
    enrich_size_mtime,
    read_logical_size_and_blob_mtime,
)
from scripts.migrate_version_csv.paths import hash_to_stored_location


def _sha1_hex(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def _slashes(path: str) -> str:
    return path.replace("\\", "/")


def test_read_logical_size_part001_matches_zipinfo_file_size(tmp_path: Path) -> None:
    payload = b"part001 sizing"
    h = _sha1_hex(payload)
    blob = tmp_path / "blob.zip"
    _write_zip(blob, {"part001": payload})

    with ZipFile(blob, "r") as zf:
        expected = zf.getinfo("part001").file_size

    size, mtime = read_logical_size_and_blob_mtime(
        blob, is_compressed=True, file_hash=h
    )
    assert size == expected == len(payload)
    assert mtime > 0


def test_read_logical_size_corrupt_zip_returns_zero_without_raising(
    tmp_path: Path,
) -> None:
    blob = tmp_path / "corrupt.zip"
    blob.write_bytes(b"not a zip file")
    h = "a" * 40
    size, mtime = read_logical_size_and_blob_mtime(
        blob, is_compressed=True, file_hash=h
    )
    assert size == 0
    assert mtime > 0


def test_read_logical_size_legacy_hash_named_matches_zipinfo_file_size(
    tmp_path: Path,
) -> None:
    payload = b"legacy zip meta"
    h = _sha1_hex(payload)
    blob = tmp_path / "legacy.zip"
    _write_zip(blob, {h: payload})

    with ZipFile(blob, "r") as zf:
        expected = zf.getinfo(h).file_size

    size, _ = read_logical_size_and_blob_mtime(blob, is_compressed=True, file_hash=h)
    assert size == expected == len(payload)


def test_enrich_size_mtime_compressed_legacy_zip(tmp_path: Path) -> None:
    payload = b"enrich-legacy-row"
    h = _sha1_hex(payload)
    data_root = tmp_path / "data"
    rel = _slashes(hash_to_stored_location(h, True))
    blob_path = data_root / rel
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    _write_zip(blob_path, {h: payload})

    out_size, out_mtime, warnings = enrich_size_mtime(
        data_root,
        h,
        rel,
        row_says_compressed=True,
        need_size=True,
        need_mtime=False,
    )
    assert out_size == len(payload)
    assert out_mtime is None
    assert not warnings


def test_enrich_size_mtime_compressed_part001_zip(tmp_path: Path) -> None:
    payload = b"enrich-part001-row"
    h = _sha1_hex(payload)
    data_root = tmp_path / "data"
    rel = _slashes(hash_to_stored_location(h, True))
    blob_path = data_root / rel
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    _write_zip(blob_path, {"part001": payload})

    out_size, out_mtime, warnings = enrich_size_mtime(
        data_root,
        h,
        rel,
        row_says_compressed=True,
        need_size=True,
        need_mtime=False,
    )
    assert out_size == len(payload)
    assert out_mtime is None
    assert not warnings
