"""Tests for `backuper.entrypoints.cli.main` dispatch and exit behavior."""

from __future__ import annotations

import sys
from unittest.mock import sentinel

import pytest
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.entrypoints.cli import main as main_mod
from backuper.models import CliUsageError, UnreachableCommandError


def test_run_with_args_dispatches_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = NewCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))
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
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))
    captured: list[UpdateCommand] = []

    def fake_run_update(c: UpdateCommand) -> None:
        captured.append(c)

    monkeypatch.setattr(main_mod, "run_update", fake_run_update)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_dispatches_verify_integrity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = VerifyIntegrityCommand(location="/b")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))
    captured: list[VerifyIntegrityCommand] = []

    def fake_run_verify_integrity(c: VerifyIntegrityCommand) -> list[str]:
        captured.append(c)
        return []

    monkeypatch.setattr(main_mod, "run_verify_integrity", fake_run_verify_integrity)
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    main_mod.run_with_args()

    assert captured == [cmd]


def test_run_with_args_dispatches_restore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cmd = RestoreCommand(location="/b", destination="/d", version_name="v")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))
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
    monkeypatch.setattr(
        main_mod.parser, "parse", lambda args: (sentinel.unknown, False)
    )
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    with pytest.raises(UnreachableCommandError, match="Unrecognized command"):
        main_mod.run_with_args()


def test_main_returns_1_for_unrecognized_command_type(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        main_mod.parser, "parse", lambda args: (sentinel.unknown, False)
    )
    monkeypatch.setattr(sys, "argv", ["backuper", "ignored"])

    assert main_mod.main() == 1
    err = capsys.readouterr().err
    assert "Unrecognized command" in err


def test_main_returns_0_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    cmd = NewCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))

    def fake_run_new(_c: NewCommand) -> None:
        return None

    monkeypatch.setattr(main_mod, "run_new", fake_run_new)
    monkeypatch.setattr(sys, "argv", ["backuper", "new", "s", "l"])

    assert main_mod.main() == 0


def test_main_returns_1_on_user_facing_error_from_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cmd = NewCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))

    def fake_run_new(_c: NewCommand) -> None:
        raise CliUsageError("bad input")

    monkeypatch.setattr(main_mod, "run_new", fake_run_new)
    monkeypatch.setattr(sys, "argv", ["backuper", "new", "s", "l"])

    assert main_mod.main() == 1
    assert capsys.readouterr().err.strip() == "bad input"


def test_main_propagates_systemexit_from_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_args: list[str]) -> tuple[object, bool]:
        raise SystemExit(3)

    monkeypatch.setattr(main_mod.parser, "parse", boom)
    monkeypatch.setattr(sys, "argv", ["backuper", "verify-integrity"])

    with pytest.raises(SystemExit) as excinfo:
        main_mod.main()
    assert excinfo.value.code == 3


def test_main_logs_and_returns_1_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cmd = NewCommand(version="v", source="s", location="l")
    monkeypatch.setattr(main_mod.parser, "parse", lambda args: (cmd, False))

    def fake_run_new(_c: NewCommand) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(main_mod, "run_new", fake_run_new)
    monkeypatch.setattr(sys, "argv", ["backuper", "new", "s", "l"])

    assert main_mod.main() == 1
    err = capsys.readouterr().err
    assert "Unhandled error" in err
    assert "RuntimeError: boom" in err
    assert "An unexpected error occurred." in err
