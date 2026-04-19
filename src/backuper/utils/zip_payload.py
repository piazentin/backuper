"""Resolve which ZIP member holds a backup payload and read it (stdlib only).

Canonical layout stores the file as ``part001``. Legacy layouts store a single
member named after the content hash (lowercase hex), matching manifest storage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from zipfile import ZipFile, ZipInfo

logger = logging.getLogger(__name__)


class ZipPayloadError(ValueError):
    """ZIP archive does not contain exactly one identifiable payload member."""


def _normalized_basename(filename: str) -> str:
    return Path(filename).name


def _file_members(zf: ZipFile) -> list[ZipInfo]:
    return [info for info in zf.infolist() if not info.is_dir()]


def resolve_zip_payload_member_name(
    zf: ZipFile,
    file_hash: str,
    *,
    zip_path: Path | None = None,
) -> str:
    """Return the ZIP member name to read for the blob identified by ``file_hash``.

    Policy:
    - Consider non-directory members only.
    - If any file member's basename is ``part001``, use that member (canonical).
      If several such members exist, raise :class:`ZipPayloadError`.
    - Else if exactly one file member's basename equals ``file_hash`` lowercased,
      use that member (legacy hash-named layout).
    - Otherwise fail with :class:`ZipPayloadError` listing member names.

    ``zip_path`` is optional and used only in error messages.
    """
    members = _file_members(zf)
    label = str(zip_path) if zip_path is not None else "<zip>"

    part001 = [
        info for info in members if _normalized_basename(info.filename) == "part001"
    ]
    if len(part001) > 1:
        names = sorted({info.filename for info in members})
        raise ZipPayloadError(
            f"{label}: multiple file members named 'part001' in archive; "
            f"expected a single payload member. Members: {names}"
        )
    if len(part001) == 1:
        return part001[0].filename

    hash_key = file_hash.lower()
    hash_named = [
        info for info in members if _normalized_basename(info.filename) == hash_key
    ]
    if len(hash_named) > 1:
        names = sorted({info.filename for info in members})
        raise ZipPayloadError(
            f"{label}: multiple file members match hash {hash_key!r}; "
            f"expected a single hash-named member. Members: {names}"
        )
    if len(hash_named) == 1:
        logger.debug(
            "Using legacy hash-named ZIP member %r in %s",
            hash_named[0].filename,
            label,
        )
        return hash_named[0].filename

    names = sorted({info.filename for info in members})
    if not names:
        raise ZipPayloadError(
            f"{label}: ZIP has no file members (empty or directory-only). "
            f"Expected a member named 'part001' or a single file member named {hash_key!r}."
        )
    raise ZipPayloadError(
        f"{label}: cannot resolve payload: expected a file member named 'part001' "
        f"or exactly one file member named {hash_key!r}. Members: {names}"
    )


def read_zip_payload_bytes(path: Path, file_hash: str) -> bytes:
    """Open ``path`` as a ZIP and return the resolved payload bytes."""
    with ZipFile(path, "r") as zf:
        member = resolve_zip_payload_member_name(zf, file_hash, zip_path=path)
        return zf.read(member)
