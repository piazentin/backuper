import argparse
import backuper.commands as c

from datetime import datetime


def _to_new_command(namespace):
    return c.NewCommand(name=namespace.name, source=namespace.source, destination=namespace.destination)


def _to_update_command(namespace):
    return c.UpdateCommand(name=namespace.name, source=namespace.source, destination=namespace.destination)


def _to_check_command(namespace):
    return c.CheckCommand(destination=namespace.destination)


def _default_name() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def parse(args):
    parser = argparse.ArgumentParser('Backup utility')
    subparsers = parser.add_subparsers(
        title='Valid commands: new, update, check')

    parser_new = subparsers.add_parser('new')
    parser_new.add_argument('source', help='Source directory to backup')
    parser_new.add_argument(
        'destination', help='Destination of the backup. Must be the name of a new directory.')
    parser_new.add_argument(
        '--name', '-n', help='Name of the version of the backup. Defaults to now\'s date time formatted as 0000-00-00T000000', dest='name', default=_default_name())
    parser_new.set_defaults(func=_to_new_command)

    parser_update = subparsers.add_parser('update')
    parser_update.add_argument('source', help='Source directory to backup')
    parser_update.add_argument(
        'destination', help='Destination of the backup. Must be the name of an existing backup directory.')
    parser_update.add_argument(
        '--name', '-n', help='Name of the version of the backup. Defaults to now\'s date time formatted as 0000-00-00T000000', dest='name', default=_default_name())
    parser_update.set_defaults(func=_to_update_command)

    parser_check = subparsers.add_parser('check')
    parser_check.add_argument(
        'destination', help='Destination of the existing backup directory')
    parser_check.set_defaults(func=_to_check_command)

    parsed = parser.parse_args(args)
    return parsed.func(parsed)
