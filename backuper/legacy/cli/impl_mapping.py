"""Translate legacy parser command objects into implementation command DTOs.

Mapping happens only here (and at this package's call sites); ``backuper.implementation``
must not import legacy command types.
"""

from backuper.implementation import commands as impl_commands
from backuper.legacy.implementation.commands import (
    CheckCommand as LegacyCheckCommand,
)
from backuper.legacy.implementation.commands import (
    NewCommand as LegacyNewCommand,
)
from backuper.legacy.implementation.commands import (
    UpdateCommand as LegacyUpdateCommand,
)


def to_implementation_new_command(
    cmd: LegacyNewCommand,
) -> impl_commands.NewCommand:
    return impl_commands.NewCommand(
        version=cmd.version,
        source=cmd.source,
        location=cmd.location,
    )


def to_implementation_update_command(
    cmd: LegacyUpdateCommand,
) -> impl_commands.UpdateCommand:
    return impl_commands.UpdateCommand(
        version=cmd.version,
        source=cmd.source,
        location=cmd.location,
    )


def to_implementation_check_command(
    cmd: LegacyCheckCommand,
) -> impl_commands.CheckCommand:
    return impl_commands.CheckCommand(location=cmd.location, version=cmd.version)
