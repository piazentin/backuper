from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from backuper.components.csv_db import _csvrow_to_model, _DirEntry, _StoredFile
from backuper.models import MalformedBackupCsvError

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


def _stored_file_to_canonical(stored_file: _StoredFile) -> CanonicalCsvFile:
    return CanonicalCsvFile(
        restore_path=stored_file.restore_path,
        sha1hash=stored_file.sha1hash,
        stored_location=stored_file.stored_location,
        is_compressed=stored_file.is_compressed,
        size=stored_file.size,
        mtime=stored_file.mtime,
    )


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
                model = _csvrow_to_model(row)
            except MalformedBackupCsvError as exc:
                raise MalformedBackupCsvError(
                    f"{path}: CSV record {record_index}: {exc} {_CANONICAL_ONLY_HINT}"
                ) from exc
            if isinstance(model, _DirEntry):
                parsed.append(CanonicalCsvDir(name=model.normalized_path()))
            else:
                parsed.append(_stored_file_to_canonical(cast(_StoredFile, model)))
    return parsed
