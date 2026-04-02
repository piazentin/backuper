from pathlib import Path
from unittest.mock import patch

import pytest

import backuper.legacy.implementation.commands as c
from backuper.implementation.commands import (
    CheckCommand as ImplCheckCommand,
    NewCommand as ImplNewCommand,
    UpdateCommand as ImplUpdateCommand,
)
from backuper.legacy.cli import (
    CHECK_ROLLBACK_ENV_VAR,
    ROLLBACK_ENV_VAR,
    UPDATE_ROLLBACK_ENV_VAR,
    run_with_args,
)


def _expected_impl_new(cmd: c.NewCommand) -> ImplNewCommand:
    return ImplNewCommand(version=cmd.version, source=cmd.source, location=cmd.location)


def _expected_impl_update(cmd: c.UpdateCommand) -> ImplUpdateCommand:
    return ImplUpdateCommand(
        version=cmd.version, source=cmd.source, location=cmd.location
    )


def _expected_impl_check(cmd: c.CheckCommand) -> ImplCheckCommand:
    return ImplCheckCommand(location=cmd.location, version=cmd.version)


@patch.dict("os.environ", {ROLLBACK_ENV_VAR: ""})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.new")
@patch("backuper.legacy.cli.implementation_cli.run_new")
def test_new_routes_to_implementation_by_default(
    implementation_new_mock, legacy_new_mock, parse_mock
):
    command = c.NewCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    implementation_new_mock.assert_called_once_with(_expected_impl_new(command))
    legacy_new_mock.assert_not_called()


@patch.dict("os.environ", {ROLLBACK_ENV_VAR: "1"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.new")
@patch("backuper.legacy.cli.implementation_cli.run_new")
def test_new_routes_to_legacy_when_rollback_enabled(
    implementation_new_mock, legacy_new_mock, parse_mock
):
    command = c.NewCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_new_mock.assert_called_once_with(command)
    implementation_new_mock.assert_not_called()


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.new")
@patch("backuper.legacy.cli.implementation_cli.run_new")
def test_new_falls_back_to_legacy_when_implementation_fails(
    implementation_new_mock, legacy_new_mock, parse_mock, capsys
):
    command = c.NewCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command
    implementation_new_mock.side_effect = RuntimeError("boom")

    run_with_args()

    implementation_new_mock.assert_called_once_with(_expected_impl_new(command))
    legacy_new_mock.assert_called_once_with(command)
    assert (
        "WARNING: implementation NEW command failed (boom); falling back to legacy NEW."
        in capsys.readouterr().err
    )


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.new")
@patch("backuper.legacy.cli.implementation_cli.run_new")
def test_new_re_raises_fallback_error_chained_from_implementation_error(
    implementation_new_mock, legacy_new_mock, parse_mock
):
    command = c.NewCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command
    implementation_error = RuntimeError("implementation boom")
    fallback_error = ValueError("legacy boom")
    implementation_new_mock.side_effect = implementation_error
    legacy_new_mock.side_effect = fallback_error

    try:
        run_with_args()
        raise AssertionError("Expected run_with_args to raise when fallback fails")
    except ValueError as raised_error:
        assert raised_error is fallback_error
        assert raised_error.__cause__ is implementation_error


@patch.dict("os.environ", {UPDATE_ROLLBACK_ENV_VAR: ""})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_routes_to_implementation_by_default(
    implementation_update_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    implementation_update_mock.assert_called_once_with(_expected_impl_update(command))
    legacy_update_mock.assert_not_called()


@patch.dict("os.environ", {UPDATE_ROLLBACK_ENV_VAR: "1"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_routes_to_legacy_when_rollback_enabled(
    implementation_update_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_update_mock.assert_called_once_with(command)
    implementation_update_mock.assert_not_called()


@patch.dict("os.environ", {UPDATE_ROLLBACK_ENV_VAR: "true"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_routes_to_legacy_when_use_legacy_env_is_true(
    implementation_update_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_update_mock.assert_called_once_with(command)
    implementation_update_mock.assert_not_called()


@patch.dict("os.environ", {UPDATE_ROLLBACK_ENV_VAR: "YES"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_routes_to_legacy_when_use_legacy_env_is_yes_uppercase(
    implementation_update_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_update_mock.assert_called_once_with(command)
    implementation_update_mock.assert_not_called()


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_falls_back_to_legacy_when_implementation_fails(
    implementation_update_mock, legacy_update_mock, parse_mock, capsys
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command
    implementation_update_mock.side_effect = RuntimeError("boom")

    run_with_args()

    implementation_update_mock.assert_called_once_with(_expected_impl_update(command))
    legacy_update_mock.assert_called_once_with(command)
    assert (
        "WARNING: implementation UPDATE command failed (boom); falling back to legacy UPDATE."
        in capsys.readouterr().err
    )


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.implementation_cli.run_update")
def test_update_re_raises_fallback_error_chained_from_implementation_error(
    implementation_update_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command
    implementation_error = RuntimeError("implementation boom")
    fallback_error = ValueError("legacy boom")
    implementation_update_mock.side_effect = implementation_error
    legacy_update_mock.side_effect = fallback_error

    try:
        run_with_args()
        raise AssertionError("Expected run_with_args to raise when fallback fails")
    except ValueError as raised_error:
        assert raised_error is fallback_error
        assert raised_error.__cause__ is implementation_error


@patch.dict("os.environ", {UPDATE_ROLLBACK_ENV_VAR: ""}, clear=False)
@patch("backuper.legacy.cli.parser.parse")
def test_update_precondition_error_falls_back_and_chains_when_legacy_also_fails(
    parse_mock, tmp_path: Path, capsys
):
    """Missing source: implementation and legacy both raise; stderr warns, cause is preserved."""
    backup = tmp_path / "backup"
    backup.mkdir()
    missing_source = tmp_path / "absent_source"
    command = c.UpdateCommand(
        version="v1",
        source=str(missing_source),
        location=str(backup),
    )
    parse_mock.return_value = command

    with pytest.raises(ValueError) as exc_info:
        run_with_args()

    raised = exc_info.value
    assert "source path" in str(raised)
    assert "does not exists" in str(raised)
    assert raised.__cause__ is not None
    assert "source path" in str(raised.__cause__)

    err = capsys.readouterr().err
    assert "WARNING: implementation UPDATE command failed" in err


@patch.dict("os.environ", {CHECK_ROLLBACK_ENV_VAR: ""})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_routes_to_implementation_by_default(
    implementation_check_mock, legacy_check_mock, parse_mock
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    implementation_check_mock.assert_called_once_with(_expected_impl_check(command))
    legacy_check_mock.assert_not_called()


@patch.dict("os.environ", {CHECK_ROLLBACK_ENV_VAR: "1"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_routes_to_legacy_when_rollback_enabled(
    implementation_check_mock, legacy_check_mock, parse_mock
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_check_mock.assert_called_once_with(command)
    implementation_check_mock.assert_not_called()


@patch.dict("os.environ", {CHECK_ROLLBACK_ENV_VAR: "true"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_routes_to_legacy_when_use_legacy_env_is_true(
    implementation_check_mock, legacy_check_mock, parse_mock
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_check_mock.assert_called_once_with(command)
    implementation_check_mock.assert_not_called()


@patch.dict("os.environ", {CHECK_ROLLBACK_ENV_VAR: "YES"})
@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_routes_to_legacy_when_use_legacy_env_is_yes_uppercase(
    implementation_check_mock, legacy_check_mock, parse_mock
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_check_mock.assert_called_once_with(command)
    implementation_check_mock.assert_not_called()


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_falls_back_to_legacy_when_implementation_fails(
    implementation_check_mock, legacy_check_mock, parse_mock, capsys
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command
    implementation_check_mock.side_effect = RuntimeError("boom")

    run_with_args()

    implementation_check_mock.assert_called_once_with(_expected_impl_check(command))
    legacy_check_mock.assert_called_once_with(command)
    assert (
        "WARNING: implementation CHECK command failed (boom); falling back to legacy CHECK."
        in capsys.readouterr().err
    )


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.check")
@patch("backuper.legacy.cli.implementation_cli.run_check")
def test_check_re_raises_fallback_error_chained_from_implementation_error(
    implementation_check_mock, legacy_check_mock, parse_mock
):
    command = c.CheckCommand(version="v1", location="/backup")
    parse_mock.return_value = command
    implementation_error = RuntimeError("implementation boom")
    fallback_error = ValueError("legacy boom")
    implementation_check_mock.side_effect = implementation_error
    legacy_check_mock.side_effect = fallback_error

    try:
        run_with_args()
        raise AssertionError("Expected run_with_args to raise when fallback fails")
    except ValueError as raised_error:
        assert raised_error is fallback_error
        assert raised_error.__cause__ is implementation_error


@patch.dict("os.environ", {CHECK_ROLLBACK_ENV_VAR: ""}, clear=False)
@patch("backuper.legacy.cli.parser.parse")
def test_check_precondition_error_falls_back_and_chains_when_legacy_also_fails(
    parse_mock, tmp_path: Path, capsys
):
    """Missing location with explicit version: fallback raises and preserves cause."""
    missing_backup = tmp_path / "absent_backup"
    command = c.CheckCommand(version="v1", location=str(missing_backup))
    parse_mock.return_value = command

    with pytest.raises(ValueError) as exc_info:
        run_with_args()

    raised = exc_info.value
    assert "Backup version named v1 does not exists" in str(raised)
    assert "does not exists" in str(raised)
    assert raised.__cause__ is not None
    assert "destination path" in str(raised.__cause__)

    err = capsys.readouterr().err
    assert "WARNING: implementation CHECK command failed" in err
