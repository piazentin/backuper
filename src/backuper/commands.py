from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NewCommand:
    version: str
    source: str
    location: str
    ignore_patterns: tuple[str, ...] = ()
    ignore_files: tuple[str, ...] = ()


@dataclass
class UpdateCommand:
    version: str
    source: str
    location: str
    ignore_patterns: tuple[str, ...] = ()
    ignore_files: tuple[str, ...] = ()


@dataclass
class VerifyIntegrityCommand:
    location: str
    version: str | None = None
    json_output: bool = False


@dataclass
class RestoreCommand:
    location: str
    destination: str
    version_name: str
