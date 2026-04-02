from dataclasses import dataclass
from typing import Optional


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
    version: Optional[str] = None
