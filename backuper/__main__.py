import sys

import backuper.argparser as parser
import backuper.backup as bkp
from backuper.commands import CheckCommand, NewCommand, UpdateCommand


def run_with_args():
    print(sys.argv)
    command = parser.parse(sys.argv[1:])
    if isinstance(command, NewCommand):
        bkp.new(command)
    elif isinstance(command, UpdateCommand):
        bkp.update(command)
    elif isinstance(command, CheckCommand):
        bkp.check(command)
    else:
        raise ValueError(f'Unrecognized command {command}')


if __name__ == "__main__":
    run_with_args()
