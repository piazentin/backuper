import sys
import os

import backuper.legacy.cli.argparser as parser
import backuper.implementation.cli as implementation_cli
import backuper.implementation.commands as impl_commands
import backuper.legacy.implementation.backup as bkp
from backuper.legacy.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)


ROLLBACK_ENV_VAR = "BACKUPER_NEW_USE_LEGACY"
UPDATE_ROLLBACK_ENV_VAR = "BACKUPER_UPDATE_USE_LEGACY"
CHECK_ROLLBACK_ENV_VAR = "BACKUPER_CHECK_USE_LEGACY"

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def _impl_new_command(cmd: NewCommand) -> impl_commands.NewCommand:
    return impl_commands.NewCommand(
        version=cmd.version,
        source=cmd.source,
        location=cmd.location,
    )


def _impl_update_command(cmd: UpdateCommand) -> impl_commands.UpdateCommand:
    return impl_commands.UpdateCommand(
        version=cmd.version,
        source=cmd.source,
        location=cmd.location,
    )


def _impl_check_command(cmd: CheckCommand) -> impl_commands.CheckCommand:
    return impl_commands.CheckCommand(location=cmd.location, version=cmd.version)


def _should_use_legacy_new() -> bool:
    return os.getenv(ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_use_legacy_update() -> bool:
    return os.getenv(UPDATE_ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_use_legacy_check() -> bool:
    return os.getenv(CHECK_ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def run_with_args():
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        if _should_use_legacy_new():
            bkp.new(command)
            return

        try:
            implementation_cli.run_new(_impl_new_command(command))
        except Exception as original_error:
            # Keep a safe rollback at runtime until NEW migration is fully stable.
            print(
                f"WARNING: implementation NEW command failed ({original_error}); falling back to legacy NEW.",
                file=sys.stderr,
            )
            try:
                bkp.new(command)
            except Exception as fallback_error:
                raise fallback_error from original_error
    elif isinstance(command, UpdateCommand):
        if _should_use_legacy_update():
            bkp.update(command)
            return

        try:
            implementation_cli.run_update(_impl_update_command(command))
        except Exception as original_error:
            # Keep a safe rollback at runtime until UPDATE migration is fully stable.
            print(
                f"WARNING: implementation UPDATE command failed ({original_error}); falling back to legacy UPDATE.",
                file=sys.stderr,
            )
            try:
                bkp.update(command)
            except Exception as fallback_error:
                raise fallback_error from original_error
    elif isinstance(command, CheckCommand):
        if _should_use_legacy_check():
            bkp.check(command)
            return

        try:
            implementation_cli.run_check(_impl_check_command(command))
        except Exception as original_error:
            # Keep a safe rollback at runtime until CHECK migration is fully stable.
            print(
                f"WARNING: implementation CHECK command failed ({original_error}); falling back to legacy CHECK.",
                file=sys.stderr,
            )
            try:
                bkp.check(command)
            except Exception as fallback_error:
                raise fallback_error from original_error
    elif isinstance(command, RestoreCommand):
        bkp.restore(command)
    else:
        raise ValueError(f"Unrecognized command {command}")
