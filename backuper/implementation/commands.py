from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NewCommand:
    version: str
    source: str
    location: str


@dataclass
class UpdateCommand:
    version: str
    source: str
    location: str


@dataclass
class CheckCommand:
    location: str
    version: str | None = None
