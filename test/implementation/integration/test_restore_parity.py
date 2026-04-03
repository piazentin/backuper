"""
RESTORE-command parity tests: implementation `run_restore` vs legacy `restore`.

For the same seeded backup (legacy `new` into two temp roots), the restored
directory trees from implementation and legacy must be identical. Assertions
mirror the spirit of `test/legacy/test_backup.py` `test_restore_with_success`
and `test_restore_with_zip` (plain blobs vs ZIP-backed blobs).
"""

from __future__ import annotations

import filecmp
from pathlib import Path

import backuper.legacy.implementation.backup as legacy_backup
import pytest
from backuper.implementation.commands import RestoreCommand
from backuper.implementation.entrypoints.cli import run_restore
from backuper.legacy.implementation.commands import (
    NewCommand,
)
from backuper.legacy.implementation.commands import (
    RestoreCommand as LegacyRestoreCommand,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESTORE_SOURCE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_new"


def _prepare_restore_source_tree() -> Path:
    """Match legacy `BackupIntegrationTest.setUp` for paths used by restore tests."""
    empty_dir = _RESTORE_SOURCE / "subdir" / "empty dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return _RESTORE_SOURCE


def _assert_restored_trees_identical(
    impl_dest: Path, legacy_dest: Path, *, label: str
) -> None:
    cmp = filecmp.dircmp(str(impl_dest), str(legacy_dest))
    assert cmp.left_only == cmp.right_only == [], label
    assert not cmp.diff_files, label


def test_restore_parity_plain_matches_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backuper.implementation.config as impl_config
    import backuper.legacy.implementation.config as legacy_config

    monkeypatch.setattr(impl_config, "ZIP_ENABLED", False)
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", False)

    fixture_source = _prepare_restore_source_tree()
    impl_backup = tmp_path / "impl_bkp"
    legacy_backup_root = tmp_path / "legacy_bkp"
    legacy_backup.new(
        NewCommand(
            version="test", source=str(fixture_source), location=str(impl_backup)
        )
    )
    legacy_backup.new(
        NewCommand(
            version="test",
            source=str(fixture_source),
            location=str(legacy_backup_root),
        )
    )

    impl_dest = tmp_path / "impl_out"
    legacy_dest = tmp_path / "legacy_out"

    run_restore(
        RestoreCommand(
            location=str(impl_backup),
            destination=str(impl_dest),
            version_name="test",
        )
    )
    legacy_backup.restore(
        LegacyRestoreCommand(
            location=str(legacy_backup_root),
            destination=str(legacy_dest),
            version_name="test",
        )
    )

    _assert_restored_trees_identical(impl_dest, legacy_dest, label="plain")


def test_restore_parity_zip_matches_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backuper.implementation.config as impl_config
    import backuper.legacy.implementation.config as legacy_config

    monkeypatch.setattr(impl_config, "ZIP_ENABLED", True)
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", True)

    fixture_source = _prepare_restore_source_tree()
    impl_backup = tmp_path / "impl_bkp"
    legacy_backup_root = tmp_path / "legacy_bkp"
    legacy_backup.new(
        NewCommand(
            version="test", source=str(fixture_source), location=str(impl_backup)
        )
    )
    legacy_backup.new(
        NewCommand(
            version="test",
            source=str(fixture_source),
            location=str(legacy_backup_root),
        )
    )

    impl_dest = tmp_path / "impl_out"
    legacy_dest = tmp_path / "legacy_out"

    run_restore(
        RestoreCommand(
            location=str(impl_backup),
            destination=str(impl_dest),
            version_name="test",
        )
    )
    legacy_backup.restore(
        LegacyRestoreCommand(
            location=str(legacy_backup_root),
            destination=str(legacy_dest),
            version_name="test",
        )
    )

    _assert_restored_trees_identical(impl_dest, legacy_dest, label="zip")
