from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from backuper.models import MalformedBackupCsvError
from backuper.utils.paths import normalize_path

_LOG = logging.getLogger(__name__)

_CANONICAL_ONLY_HINT = (
    "If this manifest needs migration from legacy row shapes, run: "
    "uv run python -m scripts.migrate_version_csv "
    "(see docs/csv-migration-contract.md)."
)


@dataclass(frozen=True)
class CanonicalCsvDir:
    name: str


@dataclass(frozen=True)
class CanonicalCsvFile:
    restore_path: str
    sha1hash: str
    stored_location: str
    is_compressed: bool
    size: int
    mtime: float


CanonicalFsObject = CanonicalCsvDir | CanonicalCsvFile


def _canonical_csv_row_to_fs_object(row: list[str]) -> CanonicalFsObject:
    """Map one canonical manifest row to a typed entry (mirrors runtime CSV semantics)."""
    if not row:
        raise MalformedBackupCsvError("Empty CSV row")
    kind = row[0]
    if kind == "d":
        return CanonicalCsvDir(name=normalize_path(row[1]))
    if kind == "f":
        if len(row) >= 7:
            _, restore_path, sha1hash, stored_location, is_compressed, size, mtime = (
                row[:7]
            )
            try:
                parsed_size = int(size) if size else 0
            except ValueError as e:
                raise MalformedBackupCsvError(
                    f"Invalid file CSV row: size field is not a valid integer: {size!r}"
                ) from e
            try:
                parsed_mtime = float(mtime) if mtime else 0.0
            except ValueError as e:
                raise MalformedBackupCsvError(
                    f"Invalid file CSV row: mtime field is not a valid float: {mtime!r}"
                ) from e
            return CanonicalCsvFile(
                restore_path=restore_path,
                sha1hash=sha1hash,
                stored_location=stored_location,
                is_compressed=is_compressed == "True",
                size=parsed_size,
                mtime=parsed_mtime,
            )
        raise MalformedBackupCsvError(
            f"Unsupported file CSV row: expected at least 7 columns "
            f"(only the first 7 fields are used when more are present), got {len(row)}"
        )
    raise MalformedBackupCsvError(f"Unknown CSV row type: {kind!r}")


def parse_canonical_version_csv(manifest_path: str | Path) -> list[CanonicalFsObject]:
    path = Path(manifest_path)
    if not path.is_file():
        raise MalformedBackupCsvError(f"Manifest is not a file: {path}")

    if path.stat().st_size == 0:
        _LOG.warning("Version manifest is empty (0 bytes): %s", path)
        return []

    parsed: list[CanonicalFsObject] = []
    record_index = 0
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.reader(file, delimiter=",", quotechar='"'):
            if not row:
                _LOG.warning(
                    "Skipping empty CSV record in version manifest (file %s)", path
                )
                continue
            record_index += 1
            kind = row[0]
            if kind == "d":
                if len(row) != 3:
                    raise MalformedBackupCsvError(
                        f"{path}: CSV record {record_index}: directory row must have "
                        f"exactly 3 columns (canonical format); got {len(row)}. "
                        f"{_CANONICAL_ONLY_HINT}"
                    )
            elif kind == "f":
                if len(row) < 7:
                    if len(row) in (3, 5):
                        raise MalformedBackupCsvError(
                            f"{path}: CSV record {record_index}: legacy short file row "
                            f"({len(row)} columns). {_CANONICAL_ONLY_HINT}"
                        )
                    raise MalformedBackupCsvError(
                        f"{path}: CSV record {record_index}: file row must have at least "
                        f"7 columns (canonical format); got {len(row)}. "
                        f"{_CANONICAL_ONLY_HINT}"
                    )
            try:
                parsed.append(_canonical_csv_row_to_fs_object(row))
            except MalformedBackupCsvError as exc:
                raise MalformedBackupCsvError(
                    f"{path}: CSV record {record_index}: {exc} {_CANONICAL_ONLY_HINT}"
                ) from exc
    return parsed
