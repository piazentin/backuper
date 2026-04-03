import os
import sys

import backuper.implementation.entrypoints.cli as implementation_cli
import backuper.legacy.cli.argparser as parser
import backuper.legacy.implementation.backup as bkp
from backuper.legacy.cli.impl_mapping import (
    to_implementation_check_command,
    to_implementation_new_command,
    to_implementation_restore_command,
    to_implementation_update_command,
)
from backuper.legacy.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)

ROLLBACK_ENV_VAR = "BACKUPER_NEW_USE_LEGACY"
UPDATE_ROLLBACK_ENV_VAR = "BACKUPER_UPDATE_USE_LEGACY"
CHECK_ROLLBACK_ENV_VAR = "BACKUPER_CHECK_USE_LEGACY"
RESTORE_ROLLBACK_ENV_VAR = "BACKUPER_RESTORE_USE_LEGACY"

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def _should_use_legacy_new() -> bool:
    return os.getenv(ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_use_legacy_update() -> bool:
    return os.getenv(UPDATE_ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_use_legacy_check() -> bool:
    return os.getenv(CHECK_ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def _should_use_legacy_restore() -> bool:
    return os.getenv(RESTORE_ROLLBACK_ENV_VAR, "").strip().lower() in _TRUTHY_ENV_VALUES


def run_with_args():
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        if _should_use_legacy_new():
            bkp.new(command)
            return

        try:
            implementation_cli.run_new(to_implementation_new_command(command))
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
            implementation_cli.run_update(to_implementation_update_command(command))
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
            implementation_cli.run_check(to_implementation_check_command(command))
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
        if _should_use_legacy_restore():
            bkp.restore(command)
            return

        try:
            implementation_cli.run_restore(to_implementation_restore_command(command))
        except Exception as original_error:
            # Keep a safe rollback at runtime until RESTORE migration is fully stable.
            print(
                f"WARNING: implementation RESTORE command failed ({original_error}); falling back to legacy RESTORE.",
                file=sys.stderr,
            )
            try:
                bkp.restore(command)
            except Exception as fallback_error:
                raise fallback_error from original_error
    else:
        raise ValueError(f"Unrecognized command {command}")
