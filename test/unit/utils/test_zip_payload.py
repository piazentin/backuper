import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest
from backuper.utils.zip_payload import (
    ZipPayloadError,
    read_zip_payload_bytes,
    resolve_zip_payload_member_name,
)


def _sha1_hex(content: bytes) -> str:
    return hashlib.sha1(content).hexdigest()


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_part001_only_reads_part001(tmp_path: Path) -> None:
    payload = b"canonical"
    path = tmp_path / "b.zip"
    _write_zip(path, {"part001": payload})
    h = _sha1_hex(payload)
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h, zip_path=path) == "part001"
    assert read_zip_payload_bytes(path, h) == payload


def test_hash_name_only_reads_hash_member(tmp_path: Path) -> None:
    payload = b"legacy-bytes"
    h = _sha1_hex(payload)
    path = tmp_path / "legacy.zip"
    _write_zip(path, {h: payload})
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h, zip_path=path) == h
    assert read_zip_payload_bytes(path, h) == payload


def test_part001_and_hash_named_prefers_part001(tmp_path: Path) -> None:
    payload_part = b"winner"
    h = _sha1_hex(payload_part)
    path = tmp_path / "both.zip"
    _write_zip(path, {"part001": payload_part, h: b"ignored"})
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h, zip_path=path) == "part001"
    assert read_zip_payload_bytes(path, h) == payload_part


def test_single_member_wrong_name_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad.zip"
    h = _sha1_hex(b"expected")
    _write_zip(path, {"not-part-not-hash.dat": b"x"})
    with ZipFile(path, "r") as zf:
        with pytest.raises(ZipPayloadError, match="cannot resolve payload"):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_multiple_file_members_no_part001_no_unique_hash_fails(tmp_path: Path) -> None:
    path = tmp_path / "multi.zip"
    h = _sha1_hex(b"sole")
    _write_zip(path, {"a.bin": b"1", "b.bin": b"2"})
    with ZipFile(path, "r") as zf:
        with pytest.raises(ZipPayloadError, match="cannot resolve payload"):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_empty_archive_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty.zip"
    with ZipFile(path, "w"):
        pass
    h = _sha1_hex(b"any")
    with ZipFile(path, "r") as zf:
        with pytest.raises(ZipPayloadError, match="no file members"):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_directory_only_noise_skipped_no_file_members_fails(tmp_path: Path) -> None:
    path = tmp_path / "dirs.zip"
    with ZipFile(path, "w") as zf:
        zf.writestr("noise/", b"")
    h = _sha1_hex(b"x")
    with ZipFile(path, "r") as zf:
        with pytest.raises(ZipPayloadError, match="no file members"):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_multiple_part001_basenames_ambiguous(tmp_path: Path) -> None:
    path = tmp_path / "two-part001.zip"
    _write_zip(
        path,
        {"a/part001": b"1", "b/part001": b"2"},
    )
    h = _sha1_hex(b"irrelevant")
    with ZipFile(path, "r") as zf:
        with pytest.raises(
            ZipPayloadError, match=r"multiple file members whose basename is 'part001'"
        ):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_multiple_hash_named_members_ambiguous(tmp_path: Path) -> None:
    h = "ab" * 20
    path = tmp_path / "dup-hash.zip"
    with ZipFile(path, "w") as zf:
        zf.writestr(f"one/{h}", b"a")
        zf.writestr(f"two/{h}", b"b")

    with ZipFile(path, "r") as zf:
        with pytest.raises(
            ZipPayloadError, match="multiple file members whose basename is"
        ):
            resolve_zip_payload_member_name(zf, h, zip_path=path)


def test_file_hash_normalized_to_lowercase_for_legacy_match(tmp_path: Path) -> None:
    payload = b"case-test"
    h_lower = _sha1_hex(payload)
    h_mixed = h_lower.upper()[:8] + h_lower[8:]
    path = tmp_path / "case.zip"
    _write_zip(path, {h_lower: payload})
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h_mixed, zip_path=path) == h_lower
    assert read_zip_payload_bytes(path, h_mixed) == payload


def test_backslash_in_member_path_normalized_like_posix(tmp_path: Path) -> None:
    """Backslashes in stored names are treated like / for basename (ZIP is POSIX-style)."""
    payload = b"slash-style"
    path = tmp_path / "bs.zip"
    with ZipFile(path, "w") as zf:
        zf.writestr("nested\\part001", payload)
    h = _sha1_hex(payload)
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h, zip_path=path) == "nested\\part001"
    assert read_zip_payload_bytes(path, h) == payload


def test_part001_in_subdirectory_resolved_by_basename(tmp_path: Path) -> None:
    payload = b"nested-part"
    path = tmp_path / "nested.zip"
    _write_zip(path, {"nested/part001": payload})
    h = _sha1_hex(payload)
    with ZipFile(path, "r") as zf:
        assert resolve_zip_payload_member_name(zf, h, zip_path=path) == "nested/part001"
    assert read_zip_payload_bytes(path, h) == payload
