"""Tests for `backuper.entrypoints.main.run_with_args` dispatch."""

from __future__ import annotations

import sys
from unittest.mock import sentinel

import pytest
from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.entrypoints import main as main_mod


def test_run_with_args_dispatches_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = NewCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: cmd)
    captured: list[NewCommand] = []

    def fake_run_new(c: NewCommand) -> None:
        captured.append(c)

    monkeypatch.setattr(main_mod, "run_new", fake_run_new)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_dispatches_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = UpdateCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: cmd)
    captured: list[UpdateCommand] = []

    def fake_run_update(c: UpdateCommand) -> None:
        captured.append(c)

    monkeypatch.setattr(main_mod, "run_update", fake_run_update)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_dispatches_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = CheckCommand(location="/b")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: cmd)
    captured: list[CheckCommand] = []

    def fake_run_check(c: CheckCommand) -> list[str]:
        captured.append(c)
        return []

    monkeypatch.setattr(main_mod, "run_check", fake_run_check)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_dispatches_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = RestoreCommand(location="/b", destination="/d", version_name="v")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: cmd)
    captured: list[RestoreCommand] = []

    def fake_run_restore(c: RestoreCommand) -> None:
        captured.append(c)

    monkeypatch.setattr(main_mod, "run_restore", fake_run_restore)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_raises_for_unrecognized_command_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: sentinel.unknown)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    with pytest.raises(ValueError, match="Unrecognized command"):
        main_mod.run_with_args()
