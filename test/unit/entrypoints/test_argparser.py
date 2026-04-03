"""Tests for `backuper.entrypoints.argparser.parse`."""

from __future__ import annotations

from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.entrypoints import argparser


def test_parse_new_command() -> None:
    cmd = argparser.parse(["new", "/path/src", "/path/dst", "--name", "my-version"])
    assert isinstance(cmd, NewCommand)
    assert cmd.source == "/path/src"
    assert cmd.location == "/path/dst"
    assert cmd.version == "my-version"


def test_parse_update_command() -> None:
    cmd = argparser.parse(["update", "/path/src", "/path/bkp", "-n", "weekly"])
    assert isinstance(cmd, UpdateCommand)
    assert cmd.source == "/path/src"
    assert cmd.location == "/path/bkp"
    assert cmd.version == "weekly"


def test_parse_check_all_versions() -> None:
    cmd = argparser.parse(["check", "/backup/root"])
    assert isinstance(cmd, CheckCommand)
    assert cmd.location == "/backup/root"
    assert cmd.version is None


def test_parse_check_single_version() -> None:
    cmd = argparser.parse(["check", "/backup/root", "--version", "v1"])
    assert isinstance(cmd, CheckCommand)
    assert cmd.location == "/backup/root"
    assert cmd.version == "v1"


def test_parse_restore_command() -> None:
    cmd = argparser.parse(
        ["restore", "/backup/root", "/restore/here", "-v", "release-1"]
    )
    assert isinstance(cmd, RestoreCommand)
    assert cmd.location == "/backup/root"
    assert cmd.destination == "/restore/here"
    assert cmd.version_name == "release-1"
