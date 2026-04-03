import sys

from backuper.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)
from backuper.implementation.entrypoints import argparser as parser
from backuper.implementation.entrypoints.cli import (
    run_check,
    run_new,
    run_restore,
    run_update,
)


def run_with_args() -> None:
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        run_new(command)
    elif isinstance(command, UpdateCommand):
        run_update(command)
    elif isinstance(command, CheckCommand):
        run_check(command)
    elif isinstance(command, RestoreCommand):
        run_restore(command)
    else:
        raise ValueError(f"Unrecognized command {command}")
