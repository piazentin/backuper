"""Stdout UX for ``run_new`` / ``run_update`` (legacy parity)."""

from __future__ import annotations

from pathlib import Path

from backuper.commands import NewCommand, UpdateCommand
from backuper.entrypoints.cli import run_new, run_update


def test_run_new_prints_analysis_banner_and_progress(tmp_path: Path, capsys) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "subdir").mkdir()
    (source / "a.txt").write_text("hello", encoding="utf-8")
    (source / "subdir" / "b.txt").write_text("world", encoding="utf-8")

    dest = tmp_path / "backup"
    run_new(
        NewCommand(version="v1", source=str(source), location=str(dest)),
    )
    out = capsys.readouterr().out

    assert f"Creating new backup from {source} into {dest}" in out
    assert "Running analysis... This may take a while." in out
    assert "+++++ BACKUP ANALYSIS RESULT FOR VERSION v1 +++++" in out
    assert "Number of directories:" in out
    assert "Number of files:" in out
    assert "Total size of files:" in out
    assert "Files to backup:" in out
    assert "Processed " in out and "of files" in out


def test_run_update_prints_opening_and_analysis(tmp_path: Path, capsys) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_text("x", encoding="utf-8")

    dest = tmp_path / "backup"
    run_new(
        NewCommand(version="v1", source=str(source), location=str(dest)),
    )
    capsys.readouterr()

    (source / "b.txt").write_text("y", encoding="utf-8")
    run_update(
        UpdateCommand(version="v2", source=str(source), location=str(dest)),
    )
    out = capsys.readouterr().out

    assert f"Updating backup at {dest} with new version v2" in out
    assert "Running analysis... This may take a while." in out
    assert "+++++ BACKUP ANALYSIS RESULT FOR VERSION v2 +++++" in out
