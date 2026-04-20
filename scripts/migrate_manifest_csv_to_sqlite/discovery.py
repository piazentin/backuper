"""Discover version manifest CSV files under a backup ``db`` directory."""

from __future__ import annotations

from pathlib import Path


def discover_csv_manifests(backup_root: Path, db_dir: str) -> list[Path]:
    """Return sorted ``*.csv`` files in ``backup_root / db_dir``.

    Rules match :mod:`scripts.migrate_version_csv`: skip non-files, names
    starting with ``.``, and non-``.csv`` suffixes (so ``._*.csv`` and
    ``.pending__…``-style dot-prefixed temps are excluded).
    """
    db_path = backup_root / db_dir
    if not db_path.is_dir():
        return []
    out: list[Path] = []
    for entry in sorted(db_path.iterdir()):
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        if entry.suffix != ".csv":
            continue
        out.append(entry)
    return out
