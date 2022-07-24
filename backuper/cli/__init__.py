import sys

import backuper.cli.argparser as parser
import backuper.implementation.backup as bkp
from backuper.implementation.commands import (
    CheckCommand,
    NewCommand,
    RestoreCommand,
    UpdateCommand,
)


def run_with_args():
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        bkp.new(command)
    elif isinstance(command, UpdateCommand):
        bkp.update(command)
    elif isinstance(command, CheckCommand):
        bkp.check(command)
    elif isinstance(command, RestoreCommand):
        bkp.restore(command)
    else:
        raise ValueError(f"Unrecognized command {command}")
