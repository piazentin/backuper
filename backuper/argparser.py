import argparse
from datetime import datetime

import backuper.commands as c


def _default_name() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def with_source_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        'source',
        help='Source directory to backup.\n'
             'This is where the data to be backuped is.'
    )


def with_destination_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        'destination',
        default=None,
        help='Destination to restore to.\n'
             'This is where your backuped data will be copied to.'
    )


def with_location_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        'location',
        help='Backup data location. This is where your data is backuped.\n'
             'Must be an empty directory for the creation of a new backup.\n'
             'Must be an existing backup directory for a restore,'
             ' check, or update.'
    )


VERSION_ARG_ALIASES = ['--name', '-n', '--version', '-v']


def with_version_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        *VERSION_ARG_ALIASES,
        dest='version',
        default=_default_name(),
        help='Optional named version of the backup.\n'
             'Defaults to now\'s datetime formatted as 0000-00-00T000000'
    )


def with_check_version_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        *VERSION_ARG_ALIASES,
        dest='version',
        default=None,
        help='Optional of the version of the backup to check.\n'
             'If not informed, will check all versions.'
    )


def with_restore_version_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        *VERSION_ARG_ALIASES,
        dest='version',
        default=None,
        required=True,
        help='Named version of the backup that will be restored.'
    )


def with_password_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        '--password', '-p',
        dest='password',
        default=None,
        help='Password used to encrypt files. '
             'If not informed, assume no password protection'
    )


def with_zip_arg(parser: argparse.ArgumentParser):
    parser.add_argument(
        '--zip', '-z',
        dest='zip',
        default=False,
        action='store_true',
        help='Optional flag to indicate either to use Zip compaction or not'
    )


def configure_new_parser(parser: argparse.ArgumentParser):
    def to_command(ns):
        return c.NewCommand(
            version=ns.version,
            source=ns.source,
            location=ns.location,
            password=ns.password,
            zip=ns.zip
        )

    with_source_arg(parser)
    with_location_arg(parser)
    with_version_arg(parser)
    with_zip_arg(parser)
    with_password_arg(parser)
    parser.set_defaults(func=to_command)


def configure_update_parser(parser: argparse.ArgumentParser):
    def to_command(ns):
        return c.UpdateCommand(
            version=ns.version,
            source=ns.source,
            location=ns.location,
            password=ns.password,
            zip=ns.zip
        )

    with_source_arg(parser)
    with_location_arg(parser)
    with_version_arg(parser)
    with_zip_arg(parser)
    with_password_arg(parser)
    parser.set_defaults(func=to_command)


def configure_check_parser(parser: argparse.ArgumentParser):
    def to_command(ns):
        return c.CheckCommand(
            location=ns.location,
            version=ns.version
        )

    with_location_arg(parser)
    with_check_version_arg(parser)
    parser.set_defaults(func=to_command)


def configure_restore_parser(parser: argparse.ArgumentParser):
    def to_command(ns):
        return c.RestoreCommand(
            location=ns.location,
            destination=ns.destination,
            version_name=ns.version,
            password=ns.password
        )

    with_location_arg(parser)
    with_destination_arg(parser)
    with_restore_version_arg(parser)
    with_password_arg(parser)
    parser.set_defaults(func=to_command)


def parse(args):
    parser = argparse.ArgumentParser('Backup utility')
    subparsers = parser.add_subparsers(
        title='Valid commands: new, update, check, restore'
    )

    configure_new_parser(subparsers.add_parser('new'))
    configure_update_parser(subparsers.add_parser('update'))
    configure_check_parser(subparsers.add_parser('check'))
    configure_restore_parser(subparsers.add_parser('restore'))

    parsed = parser.parse_args(args)
    return parsed.func(parsed)
