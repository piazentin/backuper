import argparse
from datetime import datetime

import backuper.commands as c


def _to_new_command(namespace):
    return c.NewCommand(
        name=namespace.name,
        source=namespace.source,
        destination=namespace.destination,
        zip=namespace.zip
    )


def _to_update_command(namespace):
    return c.UpdateCommand(
        name=namespace.name,
        source=namespace.source,
        destination=namespace.destination
    )


def _to_check_command(namespace):
    return c.CheckCommand(
        destination=namespace.destination,
        name=namespace.name
    )


def _to_restore_command(namespace):
    return c.RestoreCommand(
        from_source=namespace.from_source,
        to_destination=namespace.to_destination,
        version_name=namespace.version
    )


def _default_name() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def parse(args):
    parser = argparse.ArgumentParser('Backup utility')
    subparsers = parser.add_subparsers(
        title='Valid commands: new, update, check, restore')

    parser_new = subparsers.add_parser('new')
    parser_new.add_argument('source', help='Source directory to backup')
    parser_new.add_argument(
        'destination', help='Destination of the backup. Must be the name of a new directory.')
    parser_new.add_argument(
        '--name', '-n', help='Name of the version of the backup. Defaults to now\'s date time formatted as 0000-00-00T000000', dest='name', default=_default_name())
    parser_new.add_argument(
        '--zip', help='Should compact the files?', dest='zip', default=False
    )
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
    parser_check.add_argument(
        '--name', '-n', help='Optional of the version of the backup to check. If not informed, will check all versions', dest='name', default=None)
    parser_check.set_defaults(func=_to_check_command)

    parser_restore = subparsers.add_parser('restore')
    parser_restore.add_argument(
        '--from', required=True, help='Source directory containing the backup data', dest='from_source', default=None)
    parser_restore.add_argument(
        '--to', required=True, help='Empty directory in which the version of the backup will be restored to', dest="to_destination", default=None)
    parser_restore.add_argument(
        '--version', required=True, help='Version name of the backup to restore', default=None)
    parser_restore.set_defaults(func=_to_restore_command)

    parsed = parser.parse_args(args)
    return parsed.func(parsed)
