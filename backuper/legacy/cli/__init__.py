import sys
import os

import backuper.legacy.cli.argparser as parser
import backuper.implementation.cli as implementation_cli
import backuper.legacy.implementation.backup as bkp
from backuper.legacy.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)


ROLLBACK_ENV_VAR = "BACKUPER_NEW_USE_LEGACY"


def _should_use_legacy_new() -> bool:
    return os.getenv(ROLLBACK_ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def run_with_args():
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        if _should_use_legacy_new():
            bkp.new(command)
            return

        try:
            implementation_cli.run_new(command)
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
        bkp.update(command)
    elif isinstance(command, CheckCommand):
        bkp.check(command)
    elif isinstance(command, RestoreCommand):
        bkp.restore(command)
    else:
        raise ValueError(f"Unrecognized command {command}")
