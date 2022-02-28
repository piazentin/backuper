from dataclasses import dataclass
from typing import Optional


@dataclass
class NewCommand:
    name: str
    source: str
    destination: str
    password: str
    zip: bool


@dataclass
class UpdateCommand:
    name: str
    source: str
    destination: str
    password: str
    zip: bool


@dataclass
class CheckCommand:
    destination: str
    name: Optional[str] = None


@dataclass
class RestoreCommand:
    from_source: str
    to_destination: str
    version_name: str
    password: str
