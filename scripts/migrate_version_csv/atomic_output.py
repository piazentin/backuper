"""Atomic UTF-8 CSV replacement with rollback artifacts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def allocate_rollback_copy_path(csv_path: Path) -> Path:
    """Next free path: ``name.csv.bak`` or ``name.csv.bak.N`` (never overwrites)."""
    primary = csv_path.with_name(csv_path.name + ".bak")
    if not primary.exists():
        return primary
    suffix = 1
    while True:
        candidate = csv_path.with_name(f"{csv_path.name}.bak.{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def _write_bytes_fsync_replace(target_path: Path, content: bytes) -> None:
    """Write ``content`` to a temp file next to ``target_path``, fsync, then atomic rename."""
    temp_name = f".{target_path.name}.{os.getpid()}.tmp"
    temp_path = target_path.with_name(temp_name)
    try:
        with open(temp_path, "wb") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, target_path)
    except BaseException:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def write_migrated_atomic(
    csv_path: Path,
    new_text: str,
    *,
    dry_run: bool,
) -> str:
    """Persist migrated CSV or simulate. Returns ``unchanged``, ``would_change``, or ``replaced``."""
    new_bytes = new_text.encode("utf-8")
    if new_bytes == csv_path.read_bytes():
        return "unchanged"
    if dry_run:
        return "would_change"

    rollback_path = allocate_rollback_copy_path(csv_path)
    shutil.copy2(csv_path, rollback_path)
    _write_bytes_fsync_replace(csv_path, new_bytes)
    return "replaced"
