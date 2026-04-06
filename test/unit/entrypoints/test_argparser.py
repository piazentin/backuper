"""Tests for `backuper.entrypoints.argparser.parse`."""

from __future__ import annotations

import pytest
from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.entrypoints import argparser


def test_parse_new_command() -> None:
    cmd, quiet = argparser.parse(
        ["new", "/path/src", "/path/dst", "--name", "my-version"]
    )
    assert isinstance(cmd, NewCommand)
    assert quiet is False
    assert cmd.source == "/path/src"
    assert cmd.location == "/path/dst"
    assert cmd.version == "my-version"


def test_parse_update_command() -> None:
    cmd, quiet = argparser.parse(["update", "/path/src", "/path/bkp", "-n", "weekly"])
    assert isinstance(cmd, UpdateCommand)
    assert quiet is False
    assert cmd.source == "/path/src"
    assert cmd.location == "/path/bkp"
    assert cmd.version == "weekly"


def test_parse_check_all_versions() -> None:
    cmd, quiet = argparser.parse(["check", "/backup/root"])
    assert isinstance(cmd, CheckCommand)
    assert quiet is False
    assert cmd.location == "/backup/root"
    assert cmd.version is None
    assert cmd.json_output is False


def test_parse_check_single_version() -> None:
    cmd, quiet = argparser.parse(["check", "/backup/root", "--version", "v1"])
    assert isinstance(cmd, CheckCommand)
    assert quiet is False
    assert cmd.location == "/backup/root"
    assert cmd.version == "v1"


def test_parse_check_json_flag() -> None:
    cmd, quiet = argparser.parse(["check", "/backup/root", "--json"])
    assert isinstance(cmd, CheckCommand)
    assert quiet is False
    assert cmd.json_output is True


def test_parse_quiet_before_subcommand() -> None:
    cmd, quiet = argparser.parse(["--quiet", "check", "/backup/root"])
    assert isinstance(cmd, CheckCommand)
    assert quiet is True


def test_parse_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        argparser.parse([])


def test_parse_requires_subcommand_even_with_quiet() -> None:
    with pytest.raises(SystemExit):
        argparser.parse(["--quiet"])


def test_parse_restore_command() -> None:
    cmd, quiet = argparser.parse(
        ["restore", "/backup/root", "/restore/here", "-v", "release-1"]
    )
    assert isinstance(cmd, RestoreCommand)
    assert quiet is False
    assert cmd.location == "/backup/root"
    assert cmd.destination == "/restore/here"
    assert cmd.version_name == "release-1"
