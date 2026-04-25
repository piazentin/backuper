from __future__ import annotations

from pathlib import Path


class UserFacingError(Exception):
    """Base for errors that ``main()`` prints to stderr without a traceback."""


class CliUsageError(UserFacingError):
    """Invalid paths, destinations, or other CLI-level preconditions."""


class MalformedManifestRowError(UserFacingError):
    """A manifest row could not be parsed or is invalid (including migration CSV input)."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        self.detail = detail
        super().__init__(message)


class VersionAlreadyExistsError(UserFacingError):
    def __init__(self, version: str) -> None:
        self.version = version
        super().__init__(f"There is already a backup versioned with the name {version}")


class VersionNotFoundError(UserFacingError):
    """Raised when a named backup version does not exist in the database."""

    def __init__(self, name: str, *, location: Path | None = None) -> None:
        self.name = name
        self.location = location
        if location is not None:
            msg = f"Backup version named {name} does not exist at {location}"
        else:
            msg = f"Version not found: {name}"
        super().__init__(msg)


class RestorePathError(UserFacingError):
    """Restore target path is not allowed under the destination (absolute or traversal)."""


class RestoreVersionNotFoundError(UserFacingError):
    def __init__(self, version_name: str) -> None:
        self.version_name = version_name
        super().__init__(f"Backup version {version_name} does not exist in source")


class UnreachableCommandError(UserFacingError):
    """Internal: dispatch received a command type that should be impossible."""
