from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_LOG = logging.getLogger(__name__)

_VERSION_STEM_FORMAT = "%Y-%m-%dT%H%M%S"


@dataclass(frozen=True)
class InferredVersionCreatedAt:
    manifest_path: Path
    version_name: str
    # UTC epoch seconds (REAL), millisecond resolution; matches SqliteBackupDatabase.
    created_at: float


def infer_created_at_for_manifests(
    manifests: Iterable[Path],
) -> list[InferredVersionCreatedAt]:
    """Infer ``created_at`` per ADR-0004 (quantized epoch seconds for SQLite).

    - Parsable ``YYYY-MM-DDTHHMMSS`` stems are interpreted in the migration host's
      local timezone and normalized to UTC.
    - Non-parsable stems fall back to CSV file mtime.
    - Dot-prefixed filenames are ignored.
    - Collisions are logged; tie-break order is lexicographic by version name.
    """
    inferred: list[InferredVersionCreatedAt] = []
    for manifest in manifests:
        if manifest.name.startswith("."):
            continue
        version_name = manifest.stem
        parsed_s = _try_parse_version_stem_to_utc_epoch_seconds(version_name)
        if parsed_s is not None:
            created_at = parsed_s
        else:
            created_at = _quantize_epoch_seconds(manifest.stat().st_mtime)
        inferred.append(
            InferredVersionCreatedAt(
                manifest_path=manifest,
                version_name=version_name,
                created_at=created_at,
            )
        )

    inferred.sort(key=lambda item: (item.created_at, item.version_name))
    _log_collisions(inferred)
    return inferred


def _try_parse_version_stem_to_utc_epoch_seconds(stem: str) -> float | None:
    try:
        local_civil = datetime.strptime(stem, _VERSION_STEM_FORMAT)
    except ValueError:
        return None

    local_tz = datetime.now().astimezone().tzinfo
    if local_tz is None:
        return None
    as_utc = local_civil.replace(tzinfo=local_tz).astimezone(UTC)
    return _quantize_epoch_seconds(as_utc.timestamp())


def _quantize_epoch_seconds(epoch_seconds: float) -> float:
    """Match SQLite adapter: ``REAL`` epoch seconds at millisecond resolution."""
    return float(round(epoch_seconds * 1000)) / 1000.0


def _log_collisions(inferred: list[InferredVersionCreatedAt]) -> None:
    by_created_at: dict[float, list[str]] = defaultdict(list)
    for item in inferred:
        by_created_at[item.created_at].append(item.version_name)

    for created_at_s, versions in by_created_at.items():
        if len(versions) < 2:
            continue
        ordered = sorted(versions)
        _LOG.warning(
            "created_at collision at %s for versions %s; tie-break order is lexicographic by version name: %s",
            created_at_s,
            versions,
            ordered,
        )
