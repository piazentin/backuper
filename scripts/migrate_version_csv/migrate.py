"""Convert legacy version CSV rows to the canonical shape (script-local, no runtime imports)."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

from scripts.migrate_version_csv.blob_meta import enrich_size_mtime
from scripts.migrate_version_csv.paths import hash_to_stored_location, normalize_path


@dataclass(frozen=True)
class MigrateError(Exception):
    path: Path
    row: int
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.row}: {self.reason}"


@dataclass(frozen=True)
class _PendingFileRow:
    """Intermediate state: CSV fields plus what still needs blob enrichment (if anything)."""

    restore_path: str
    sha1hash: str
    stored_location: str
    is_compressed: bool
    size: int | None
    mtime: float | None
    blob_compression_preference: bool | None


def _csv_row_line(fields: list[object]) -> str:
    """Serialize one CSV row with proper quoting/escaping (round-trips with ``csv.reader``)."""
    buf = io.StringIO()
    writer = csv.writer(
        buf,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_ALL,
        lineterminator="\n",
    )
    writer.writerow(fields)
    return buf.getvalue()


def _format_directory_line(normalized_path: str) -> str:
    return _csv_row_line(["d", normalized_path, ""])


def _format_file_line(
    restore_path: str,
    sha1hash: str,
    stored_location: str,
    is_compressed: bool,
    size: int,
    mtime: float,
) -> str:
    return _csv_row_line(
        [
            "f",
            restore_path,
            sha1hash,
            stored_location,
            "True" if is_compressed else "False",
            size,
            mtime,
        ]
    )


def _parse_csv_bool(raw: str) -> bool:
    return raw == "True"


def _parse_int_field(
    raw: str,
    *,
    version_path: Path,
    row_index: int,
    field_name: str,
) -> int:
    try:
        return int(raw)
    except ValueError as e:
        raise MigrateError(
            version_path,
            row_index,
            f"invalid {field_name} field (expected integer): {raw!r}",
        ) from e


def _parse_float_field(
    raw: str,
    *,
    version_path: Path,
    row_index: int,
    field_name: str,
) -> float:
    try:
        return float(raw)
    except ValueError as e:
        raise MigrateError(
            version_path,
            row_index,
            f"invalid {field_name} field (expected float): {raw!r}",
        ) from e


def _parse_file_row_to_pending(
    row: list[str],
    *,
    version_path: Path,
    row_index: int,
) -> _PendingFileRow:
    """Map 3-, 5-, or 7-column file rows into a single pending representation."""
    column_count = len(row)
    if column_count == 3:
        _kind, restore_path, sha1hash = row
        return _PendingFileRow(
            restore_path=restore_path,
            sha1hash=sha1hash,
            stored_location=hash_to_stored_location(sha1hash, False),
            is_compressed=False,
            size=None,
            mtime=None,
            blob_compression_preference=False,
        )
    if column_count == 5:
        _kind, restore_path, sha1hash, stored_location, compressed_raw = row
        is_compressed = _parse_csv_bool(compressed_raw)
        return _PendingFileRow(
            restore_path=restore_path,
            sha1hash=sha1hash,
            stored_location=stored_location,
            is_compressed=is_compressed,
            size=None,
            mtime=None,
            blob_compression_preference=is_compressed,
        )
    if column_count >= 7:
        (
            _kind,
            restore_path,
            sha1hash,
            stored_location,
            compressed_raw,
            size_raw,
            mtime_raw,
        ) = row[:7]
        is_compressed = _parse_csv_bool(compressed_raw)
        size: int | None
        mtime: float | None
        if size_raw == "":
            size = None
        else:
            size = _parse_int_field(
                size_raw,
                version_path=version_path,
                row_index=row_index,
                field_name="size",
            )
        if mtime_raw == "":
            mtime = None
        else:
            mtime = _parse_float_field(
                mtime_raw,
                version_path=version_path,
                row_index=row_index,
                field_name="mtime",
            )
        return _PendingFileRow(
            restore_path=restore_path,
            sha1hash=sha1hash,
            stored_location=stored_location,
            is_compressed=is_compressed,
            size=size,
            mtime=mtime,
            blob_compression_preference=is_compressed,
        )

    raise MigrateError(
        version_path,
        row_index,
        f"unsupported file row column count {column_count} (expected 3, 5, or >=7)",
    )


def _finalize_pending_file_row(
    pending: _PendingFileRow,
    *,
    data_root: Path,
    version_path: Path,
    row_index: int,
) -> tuple[str, list[str]]:
    """Apply blob enrichment for missing size/mtime, then emit one canonical line."""
    if pending.size is not None and pending.mtime is not None:
        line = _format_file_line(
            pending.restore_path,
            pending.sha1hash,
            pending.stored_location,
            pending.is_compressed,
            pending.size,
            pending.mtime,
        )
        return line, []

    need_size = pending.size is None
    need_mtime = pending.mtime is None
    enriched_size, enriched_mtime, blob_warnings = enrich_size_mtime(
        data_root,
        pending.sha1hash,
        pending.stored_location,
        pending.blob_compression_preference,
        need_size=need_size,
        need_mtime=need_mtime,
    )
    final_size = pending.size if pending.size is not None else enriched_size
    final_mtime = pending.mtime if pending.mtime is not None else enriched_mtime
    if final_size is None:
        final_size = 0
    if final_mtime is None:
        final_mtime = 0.0

    prefixed = [f"{version_path}:{row_index}: {message}" for message in blob_warnings]
    line = _format_file_line(
        pending.restore_path,
        pending.sha1hash,
        pending.stored_location,
        pending.is_compressed,
        final_size,
        final_mtime,
    )
    return line, prefixed


def _migrate_file_row(
    row: list[str],
    *,
    data_root: Path,
    row_index: int,
    version_path: Path,
) -> tuple[str, list[str]]:
    pending = _parse_file_row_to_pending(
        row,
        version_path=version_path,
        row_index=row_index,
    )
    return _finalize_pending_file_row(
        pending,
        data_root=data_root,
        version_path=version_path,
        row_index=row_index,
    )


def _migrate_directory_row(
    row: list[str],
    *,
    row_index: int,
    version_path: Path,
) -> str:
    column_count = len(row)
    if column_count < 2:
        raise MigrateError(
            version_path,
            row_index,
            f"directory row needs at least 2 columns, got {column_count}",
        )
    raw_path = row[1]
    normalized = normalize_path(raw_path)
    return _format_directory_line(normalized)


def migrate_version_csv_text(
    text: str,
    *,
    data_root: Path,
    version_path: Path,
) -> tuple[str, list[str]]:
    """Return migrated UTF-8 text (newline-terminated lines) and warning lines."""
    output_chunks: list[str] = []
    all_warnings: list[str] = []
    reader = csv.reader(io.StringIO(text), delimiter=",", quotechar='"')
    for row_index, row in enumerate(reader, start=1):
        if not row:
            raise MigrateError(version_path, row_index, "empty CSV row")
        kind = row[0]
        if kind == "d":
            output_chunks.append(
                _migrate_directory_row(
                    row,
                    row_index=row_index,
                    version_path=version_path,
                )
            )
        elif kind == "f":
            line, row_warnings = _migrate_file_row(
                row,
                data_root=data_root,
                row_index=row_index,
                version_path=version_path,
            )
            output_chunks.append(line)
            all_warnings.extend(row_warnings)
        else:
            raise MigrateError(
                version_path,
                row_index,
                f"unknown CSV row kind {kind!r} (expected 'd' or 'f')",
            )
    return "".join(output_chunks), all_warnings


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")
