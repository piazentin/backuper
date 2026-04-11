"""Tests for `backuper.entrypoints.cli.argparser.parse`."""

from __future__ import annotations

import pytest
from backuper.commands import (
    NewCommand,
    RestoreCommand,
    UpdateCommand,
    VerifyIntegrityCommand,
)
from backuper.entrypoints.cli import argparser


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


def test_parse_verify_integrity_all_versions() -> None:
    cmd, quiet = argparser.parse(["verify-integrity", "/backup/root"])
    assert isinstance(cmd, VerifyIntegrityCommand)
    assert quiet is False
    assert cmd.location == "/backup/root"
    assert cmd.version is None
    assert cmd.json_output is False


def test_parse_verify_integrity_single_version() -> None:
    cmd, quiet = argparser.parse(
        ["verify-integrity", "/backup/root", "--version", "v1"]
    )
    assert isinstance(cmd, VerifyIntegrityCommand)
    assert quiet is False
    assert cmd.location == "/backup/root"
    assert cmd.version == "v1"


def test_parse_verify_integrity_json_flag() -> None:
    cmd, quiet = argparser.parse(["verify-integrity", "/backup/root", "--json"])
    assert isinstance(cmd, VerifyIntegrityCommand)
    assert quiet is False
    assert cmd.json_output is True


def test_parse_quiet_before_subcommand() -> None:
    cmd, quiet = argparser.parse(["--quiet", "verify-integrity", "/backup/root"])
    assert isinstance(cmd, VerifyIntegrityCommand)
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
