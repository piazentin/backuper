from dataclasses import dataclass


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
