from dataclasses import dataclass
from typing import Optional


@dataclass
class NewCommand:
    name: str
    source: str
    destination: str


@dataclass
class UpdateCommand:
    name: str
    source: str
    destination: str


@dataclass
class CheckCommand:
    destination: str
    name: Optional[str] = None
