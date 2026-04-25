from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from backuper.components.backup_analyzer import BackupAnalyzerImpl
from backuper.components.file_reader import LocalFileReader
from backuper.components.filestore import LocalFileStore
from backuper.components.path_ignore import GitIgnorePathFilter
from backuper.components.reporter import NoOpAnalysisReporter
from backuper.components.sqlite_db import SqliteBackupDatabase, SqliteDb
from backuper.config import FilestoreConfig, SqliteDbConfig
from backuper.controllers.backup import new_backup

_REPO_ROOT = Path(__file__).resolve().parents[2]
_IGNORE_FIXTURE = _REPO_ROOT / "test" / "resources" / "bkp_test_sources_ignore_rules"
_EXPECTED_PHASE1_MANIFEST_PATHS = {
    Path(".gitignore"),
    Path("kept.txt"),
    Path("layered_dir"),
    Path("user_override/kept_by_root.txt"),
    Path("user_override"),
    Path("layered_dir/.backupignore"),
    Path("layered_dir/outer.txt"),
    Path("negation_dir"),
    Path("negation_dir/reincluded.txt"),
}


def _copy_ignore_fixture(tmp_path: Path) -> Path:
    destination = tmp_path / "bkp_test_sources_ignore_rules"
    shutil.copytree(_IGNORE_FIXTURE, destination)
    return destination


async def _run_backup_and_list_manifest_paths(
    source: Path, destination: Path, *, user_patterns: tuple[str, ...] = ()
) -> set[Path]:
    db = SqliteBackupDatabase(SqliteDb(SqliteDbConfig(backup_dir=str(destination))))
    await new_backup(
        source,
        "ignore-testing",
        file_reader=LocalFileReader(
            path_filter=GitIgnorePathFilter(user_patterns=user_patterns)
        ),
        analyzer=BackupAnalyzerImpl(),
        db=db,
        filestore=LocalFileStore(
            FilestoreConfig(
                backup_dir=str(destination),
                zip_enabled=False,
            )
        ),
        reporter=NoOpAnalysisReporter(),
    )

    manifest_paths: set[Path] = set()
    async for item in db.list_files("ignore-testing"):
        manifest_paths.add(item.relative_path)
    return manifest_paths


@pytest.mark.asyncio
async def test_source_ignore_phase2_p21_keeps_phase1_inclusion_set(
    tmp_path: Path,
) -> None:
    source = _copy_ignore_fixture(tmp_path)
    destination = tmp_path / "backup"

    manifest_paths = await _run_backup_and_list_manifest_paths(source, destination)

    assert manifest_paths == _EXPECTED_PHASE1_MANIFEST_PATHS


@pytest.mark.asyncio
async def test_source_ignore_phase2_p22_negation_keeps_descent_for_reinclusion(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = _copy_ignore_fixture(tmp_path)
    destination = tmp_path / "backup"
    caplog.set_level("INFO", logger="backuper.components.file_reader")

    manifest_paths = await _run_backup_and_list_manifest_paths(source, destination)

    assert Path("negation_dir/reincluded.txt") in manifest_paths

    messages = [record.getMessage() for record in caplog.records]
    assert all("Skipping negation_dir" not in msg for msg in messages)
    assert all("Skipping negation_dir/reincluded.txt" not in msg for msg in messages)


@pytest.mark.asyncio
async def test_source_ignore_skip_logs_user_and_tree_reasons_in_caplog(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Full backup path: skip lines distinguish CLI user patterns vs tree ignore files."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "by_user.txt").write_text("u", encoding="utf-8")
    (source / "by_tree.txt").write_text("t", encoding="utf-8")
    (source / "kept.txt").write_text("k", encoding="utf-8")
    (source / ".gitignore").write_text("by_tree.txt\n", encoding="utf-8")
    destination = tmp_path / "backup"
    caplog.set_level("INFO", logger="backuper.components.file_reader")

    manifest_paths = await _run_backup_and_list_manifest_paths(
        source, destination, user_patterns=("by_user.txt",)
    )

    assert Path(".gitignore") in manifest_paths
    assert Path("kept.txt") in manifest_paths
    assert Path("by_user.txt") not in manifest_paths
    assert Path("by_tree.txt") not in manifest_paths
    messages = [record.getMessage() for record in caplog.records]
    user_logs = [msg for msg in messages if "Skipping by_user.txt" in msg]
    tree_logs = [msg for msg in messages if "Skipping by_tree.txt" in msg]
    assert len(user_logs) == 1
    assert "excluded by user" in user_logs[0]
    assert len(tree_logs) == 1
    assert "excluded by .gitignore" in tree_logs[0]


@pytest.mark.asyncio
async def test_source_ignores_skip_file_and_directory_with_single_boundary_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    source = _copy_ignore_fixture(tmp_path)
    destination = tmp_path / "backup"
    caplog.set_level("INFO", logger="backuper.components.file_reader")

    manifest_paths = await _run_backup_and_list_manifest_paths(source, destination)

    assert Path("kept.txt") in manifest_paths
    assert Path("user_override/kept_by_root.txt") in manifest_paths
    assert Path("layered_dir/outer.txt") in manifest_paths
    assert Path("layered_dir/inner.txt") not in manifest_paths
    assert Path("negation_dir/reincluded.txt") in manifest_paths

    messages = [record.getMessage() for record in caplog.records]
    assert sum("Skipping layered_dir/inner.txt" in msg for msg in messages) == 1
    layered_inner_logs = [
        msg for msg in messages if "Skipping layered_dir/inner.txt" in msg
    ]
    assert any(
        "excluded by layered_dir/.backupignore" in msg for msg in layered_inner_logs
    )
    assert all("layered_dir/outer.txt" not in msg for msg in messages)


@pytest.mark.asyncio
async def test_source_ignore_precedence_and_symlink_directory_not_followed(
    tmp_path: Path,
) -> None:
    source = _copy_ignore_fixture(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.txt").write_text("outside", encoding="utf-8")
    symlink_path = source / "linked_dir"
    try:
        os.symlink(external, symlink_path, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks are not supported in this environment")

    destination = tmp_path / "backup"
    manifest_paths = await _run_backup_and_list_manifest_paths(
        source,
        destination,
        user_patterns=("user_override/**", "layered_dir/**"),
    )

    assert Path("user_override/kept_by_root.txt") in manifest_paths
    assert Path("layered_dir/outer.txt") in manifest_paths
    assert Path("layered_dir/inner.txt") not in manifest_paths
    assert Path("linked_dir/outside.txt") not in manifest_paths
