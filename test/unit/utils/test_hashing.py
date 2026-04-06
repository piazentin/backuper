import hashlib
from pathlib import Path

from backuper.utils.hashing import compute_hash


def test_compute_hash_uses_full_file_contents(tmp_path: Path) -> None:
    content = b"chunk-boundary-test" * 50
    path = tmp_path / "blob"
    path.write_bytes(content)
    assert compute_hash(path, buffer_size=64) == hashlib.sha1(content).hexdigest()
