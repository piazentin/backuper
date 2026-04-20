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
    created_at_ms: float


def infer_created_at_for_manifests(
    manifests: Iterable[Path],
) -> list[InferredVersionCreatedAt]:
    """Infer ``created_at`` (UTC epoch ms) per ADR-0004.

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
        parsed_ms = _try_parse_version_stem_to_utc_epoch_ms(version_name)
        if parsed_ms is not None:
            created_at_ms = parsed_ms
        else:
            created_at_ms = _to_epoch_millis(manifest.stat().st_mtime)
        inferred.append(
            InferredVersionCreatedAt(
                manifest_path=manifest,
                version_name=version_name,
                created_at_ms=created_at_ms,
            )
        )

    inferred.sort(key=lambda item: (item.created_at_ms, item.version_name))
    _log_collisions(inferred)
    return inferred


def _try_parse_version_stem_to_utc_epoch_ms(stem: str) -> float | None:
    try:
        local_civil = datetime.strptime(stem, _VERSION_STEM_FORMAT)
    except ValueError:
        return None

    local_tz = datetime.now().astimezone().tzinfo
    if local_tz is None:
        return None
    as_utc = local_civil.replace(tzinfo=local_tz).astimezone(UTC)
    return _to_epoch_millis(as_utc.timestamp())


def _to_epoch_millis(epoch_seconds: float) -> float:
    # Keep integer-ms precision in REAL storage.
    return float(round(epoch_seconds * 1000))


def _log_collisions(inferred: list[InferredVersionCreatedAt]) -> None:
    by_created_at: dict[float, list[str]] = defaultdict(list)
    for item in inferred:
        by_created_at[item.created_at_ms].append(item.version_name)

    for created_at_ms, versions in by_created_at.items():
        if len(versions) < 2:
            continue
        ordered = sorted(versions)
        _LOG.warning(
            "created_at collision at %sms for versions %s; tie-break order is lexicographic by version name: %s",
            int(created_at_ms),
            versions,
            ordered,
        )
