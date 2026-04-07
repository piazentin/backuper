import logging
import sys

from backuper.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.entrypoints import argparser as parser
from backuper.entrypoints.cli import (
    run_check,
    run_new,
    run_restore,
    run_update,
)
from backuper.models import UnreachableCommandError, UserFacingError

_LOG = logging.getLogger("backuper")


def _configure_logging(quiet: bool) -> None:
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        force=True,
    )


def dispatch_command(
    command: NewCommand | UpdateCommand | CheckCommand | RestoreCommand,
) -> None:
    if isinstance(command, NewCommand):
        run_new(command)
    elif isinstance(command, UpdateCommand):
        run_update(command)
    elif isinstance(command, CheckCommand):
        run_check(command)
    elif isinstance(command, RestoreCommand):
        run_restore(command)
    else:
        raise UnreachableCommandError(f"Unrecognized command {command}")


def run_with_args() -> None:
    command, quiet = parser.parse(sys.argv[1:])
    _configure_logging(quiet)
    dispatch_command(command)


def main() -> int:
    try:
        command, quiet = parser.parse(sys.argv[1:])
        _configure_logging(quiet)
        dispatch_command(command)
    except SystemExit:
        raise
    except UserFacingError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception:
        _LOG.exception("Unhandled error")
        print("An unexpected error occurred.", file=sys.stderr)
        return 1
    return 0
