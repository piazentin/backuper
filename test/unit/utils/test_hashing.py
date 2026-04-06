import hashlib
from pathlib import Path

from backuper.utils.hashing import compute_hash


def test_compute_hash_small_file_hashes_entire_content(tmp_path: Path) -> None:
    content = b"fits-in-one-read"
    path = tmp_path / "blob"
    path.write_bytes(content)
    assert compute_hash(path, buffer_size=64) == hashlib.sha1(content).hexdigest()


def test_compute_hash_large_file_matches_legacy_first_chunk_only(
    tmp_path: Path,
) -> None:
    buffer_size = 64
    content = b"x" * (buffer_size + 10)
    path = tmp_path / "blob"
    path.write_bytes(content)
    expected = hashlib.sha1(content[:buffer_size]).hexdigest()
    assert compute_hash(path, buffer_size=buffer_size) == expected
