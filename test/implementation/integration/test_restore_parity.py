"""
RESTORE-command parity tests: implementation `run_restore` vs legacy `restore`.

For the same seeded backup (legacy `new` into two temp roots), the restored
directory trees from implementation and legacy must be identical. Assertions
mirror the spirit of `test/legacy/test_backup.py` `test_restore_with_success`
and `test_restore_with_zip` (plain blobs vs ZIP-backed blobs).
"""

from __future__ import annotations

import filecmp
import shutil
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


def _prepare_restore_source_tree(tmp_path: Path) -> Path:
    """Match legacy `BackupIntegrationTest.setUp` for paths used by restore tests."""
    copied = tmp_path / "restore_source"
    shutil.copytree(_RESTORE_SOURCE, copied)
    empty_dir = copied / "subdir" / "empty dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    return copied


def _assert_restored_trees_identical(
    impl_dest: Path, legacy_dest: Path, *, label: str
) -> None:
    def compare(left: Path, right: Path) -> None:
        left_names = sorted(p.name for p in left.iterdir())
        right_names = sorted(p.name for p in right.iterdir())
        assert left_names == right_names, f"{label}: {left} vs {right}"
        for name in left_names:
            lp = left / name
            rp = right / name
            if lp.is_symlink() or rp.is_symlink():
                raise AssertionError(f"{label}: unexpected symlink {lp} vs {rp}")
            if lp.is_dir() and rp.is_dir():
                compare(lp, rp)
            elif lp.is_file() and rp.is_file():
                assert filecmp.cmp(lp, rp, shallow=False), f"{label}: {lp} vs {rp}"
            else:
                raise AssertionError(f"{label}: entry kind mismatch {lp} vs {rp}")

    compare(impl_dest, legacy_dest)


def test_restore_parity_plain_matches_legacy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backuper.implementation.config as impl_config
    import backuper.legacy.implementation.config as legacy_config

    monkeypatch.setattr(impl_config, "ZIP_ENABLED", False)
    monkeypatch.setattr(legacy_config, "ZIP_ENABLED", False)

    fixture_source = _prepare_restore_source_tree(tmp_path)
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

    fixture_source = _prepare_restore_source_tree(tmp_path)
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
