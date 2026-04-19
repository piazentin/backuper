from pathlib import Path
from zipfile import ZipFile

from backuper.components.filestore import LocalFileStore
from backuper.config import FilestoreConfig
from backuper.utils.hashing import compute_hash
from backuper.utils.paths import hash_to_stored_location


def test_local_filestore_put_and_dedup_exists_branch(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"hello world")

    backup_root = tmp_path / "backup"
    store = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )

    first = store.put(source, Path("nested/source.txt"))
    second = store.put(source, Path("nested/source.txt"), precomputed_hash=first.hash)

    assert first.is_compressed is False
    assert second.stored_location == first.stored_location
    assert second.hash == first.hash
    assert second.restore_path == "nested/source.txt"

    stored_file = backup_root / "data" / first.stored_location
    assert stored_file.exists()
    assert stored_file.read_bytes() == b"hello world"


def test_local_filestore_put_compressed_content(tmp_path: Path) -> None:
    source = tmp_path / "doc.txt"
    source.write_bytes(b"compress me")

    backup_root = tmp_path / "backup"
    store = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=True,
            zip_min_filesize_in_bytes=1,
            zip_skip_extensions=set(),
        )
    )

    stored = store.put(source, Path("doc.txt"))

    assert stored.is_compressed is True
    assert stored.stored_location.endswith(".zip")

    zip_path = backup_root / "data" / stored.stored_location
    assert zip_path.exists()
    with ZipFile(zip_path, "r") as zip_archive:
        assert zip_archive.namelist() == ["part001"]
        assert zip_archive.read("part001") == b"compress me"


def test_local_filestore_read_blob_part001_after_put(tmp_path: Path) -> None:
    source = tmp_path / "doc.txt"
    source.write_bytes(b"read via part001")

    backup_root = tmp_path / "backup"
    store = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=True,
            zip_min_filesize_in_bytes=1,
            zip_skip_extensions=set(),
        )
    )

    stored = store.put(source, Path("doc.txt"))
    assert stored.is_compressed is True
    assert store.read_blob(stored.hash, True) == b"read via part001"


def test_local_filestore_read_blob_legacy_hash_named_zip(tmp_path: Path) -> None:
    source = tmp_path / "legacy.txt"
    payload = b"legacy blob bytes"
    source.write_bytes(payload)
    file_hash = compute_hash(source)

    backup_root = tmp_path / "backup"
    rel = hash_to_stored_location(file_hash, is_compressed=True)
    zip_path = backup_root / "data" / rel
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(zip_path, "w") as zf:
        zf.writestr(file_hash, payload)

    store = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=True,
        )
    )

    assert store.read_blob(file_hash, True) == payload


def test_publish_staged_blob_discards_duplicate_staged_file(tmp_path: Path) -> None:
    backup_root = tmp_path / "backup"
    store = LocalFileStore(
        FilestoreConfig(
            backup_dir=str(backup_root),
            zip_enabled=False,
        )
    )

    staged_blob_path = backup_root / "data" / "staged"
    staged_blob_path.write_bytes(b"staged")

    content_address_path = backup_root / "data" / "a" / "b" / "c" / "d" / "hash"
    content_address_path.parent.mkdir(parents=True, exist_ok=True)
    content_address_path.write_bytes(b"already present")

    store._publish_staged_blob_if_absent(staged_blob_path, content_address_path)

    assert not staged_blob_path.exists()
    assert content_address_path.read_bytes() == b"already present"
