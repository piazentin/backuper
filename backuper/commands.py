from dataclasses import dataclass
from typing import Optional


@dataclass
class NewCommand:
    name: str
    source: str
    destination: str
    zip: bool


@dataclass
class UpdateCommand:
    # TODO add zip flag do update
    name: str
    source: str
    destination: str


@dataclass
class CheckCommand:
    destination: str
    name: Optional[str] = None


@dataclass
class RestoreCommand:
    from_source: str
    to_destination: str
    version_name: str
