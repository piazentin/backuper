from unittest.mock import patch

import backuper.legacy.implementation.commands as c
from backuper.legacy.cli import ROLLBACK_ENV_VAR, run_with_args


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

    implementation_new_mock.assert_called_once_with(command)
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

    implementation_new_mock.assert_called_once_with(command)
    legacy_new_mock.assert_called_once_with(command)
    assert "WARNING: implementation NEW command failed (boom); falling back to legacy NEW." in capsys.readouterr().err


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


@patch("backuper.legacy.cli.parser.parse")
@patch("backuper.legacy.cli.bkp.update")
@patch("backuper.legacy.cli.bkp.new")
@patch("backuper.legacy.cli.implementation_cli.run_new")
def test_update_stays_on_legacy_path(
    implementation_new_mock, legacy_new_mock, legacy_update_mock, parse_mock
):
    command = c.UpdateCommand(version="v1", source="/source", location="/backup")
    parse_mock.return_value = command

    run_with_args()

    legacy_update_mock.assert_called_once_with(command)
    implementation_new_mock.assert_not_called()
    legacy_new_mock.assert_not_called()
