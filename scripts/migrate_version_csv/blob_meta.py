"""Derive size/mtime from on-disk blobs (aligned with ``LocalFileStore`` layout)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile

from backuper.utils.zip_payload import ZipPayloadError, resolve_zip_payload_member_name

from scripts.migrate_version_csv.paths import hash_to_stored_location

_LOG = logging.getLogger(__name__)


def read_logical_size_and_blob_mtime(
    blob_path: Path,
    *,
    is_compressed: bool,
    file_hash: str | None = None,
) -> tuple[int, float]:
    """Logical uncompressed size and the blob file's mtime.

    For compressed blobs, pass ``file_hash`` (manifest SHA-1 hex); member resolution matches
    ``backuper.utils.zip_payload`` (same rules as restore).
    """
    if not blob_path.is_file():
        return 0, 0.0
    blob_mtime = os.path.getmtime(blob_path)
    if not is_compressed:
        return os.path.getsize(blob_path), blob_mtime
    if not file_hash:
        _LOG.warning(
            "Compressed blob enrichment needs file_hash for ZIP resolution: %s",
            blob_path,
        )
        return 0, blob_mtime
    try:
        with ZipFile(blob_path, "r") as archive:
            try:
                member_name = resolve_zip_payload_member_name(
                    archive, file_hash, zip_path=blob_path
                )
            except ZipPayloadError as exc:
                _LOG.warning("%s", exc)
                return 0, blob_mtime
            member = archive.getinfo(member_name)
            return member.file_size, blob_mtime
    except (OSError, BadZipFile, LargeZipFile) as exc:
        _LOG.warning("Cannot read ZIP blob %s: %s", blob_path, exc)
        return 0, blob_mtime


def _slashes(path: str) -> str:
    return path.replace("\\", "/")


def resolve_blob_for_enrichment(
    data_root: Path,
    sha1hash: str,
    stored_location: str,
    row_says_compressed: bool | None,
) -> tuple[Path, bool] | None:
    """Pick one on-disk blob for this hash, or ``None`` if neither exists."""
    rel_uncompressed = _slashes(hash_to_stored_location(sha1hash, False))
    rel_compressed = _slashes(hash_to_stored_location(sha1hash, True))
    path_uncompressed = data_root / rel_uncompressed
    path_compressed = data_root / rel_compressed
    has_uncompressed = path_uncompressed.is_file()
    has_compressed = path_compressed.is_file()

    stored = _slashes(stored_location)
    if stored == rel_uncompressed and has_uncompressed:
        return path_uncompressed, False
    if stored == rel_compressed and has_compressed:
        return path_compressed, True

    if has_uncompressed and not has_compressed:
        return path_uncompressed, False
    if has_compressed and not has_uncompressed:
        return path_compressed, True
    if has_uncompressed and has_compressed:
        if row_says_compressed is not None:
            chosen_compressed = row_says_compressed
            chosen_path = path_compressed if chosen_compressed else path_uncompressed
            return chosen_path, chosen_compressed
        _LOG.warning(
            "Both compressed and uncompressed blobs exist for hash %s; "
            "preferring uncompressed for enrichment",
            sha1hash,
        )
        return path_uncompressed, False
    return None


def enrich_size_mtime(
    data_root: Path,
    sha1hash: str,
    stored_location: str,
    row_says_compressed: bool | None,
    *,
    need_size: bool,
    need_mtime: bool,
) -> tuple[int | None, float | None, list[str]]:
    """Fill missing size and/or mtime from blob; ``None`` means caller keeps CSV value."""
    warnings: list[str] = []
    if not need_size and not need_mtime:
        raise RuntimeError("enrich_size_mtime requires at least one missing field")

    resolved = resolve_blob_for_enrichment(
        data_root,
        sha1hash,
        stored_location,
        row_says_compressed,
    )
    if resolved is None:
        warnings.append(
            f"no blob on disk for hash {sha1hash!r} (stored_location={stored_location!r})"
        )
        return (
            (0 if need_size else None),
            (0.0 if need_mtime else None),
            warnings,
        )

    blob_path, blob_is_compressed = resolved
    logical_size, blob_mtime = read_logical_size_and_blob_mtime(
        blob_path,
        is_compressed=blob_is_compressed,
        file_hash=sha1hash,
    )
    out_size = logical_size if need_size else None
    out_mtime = blob_mtime if need_mtime else None
    return out_size, out_mtime, warnings
