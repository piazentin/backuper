from dataclasses import dataclass
from typing import Optional


@dataclass
class NewCommand:
    version: str
    source: str
    location: str
    password: str
    zip: bool


@dataclass
class UpdateCommand:
    version: str
    source: str
    location: str
    password: str
    zip: bool


@dataclass
class CheckCommand:
    location: str
    version: Optional[str] = None


@dataclass
class RestoreCommand:
    location: str
    destination: str
    version_name: str
    password: str
