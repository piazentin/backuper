import base64
import os

DEFAULT_ENCODING = "UTF-8"


def normalize_path(path: str) -> str:
    return "/".join(path.replace("\\", "/").strip("/").split("/"))


def to_base64str(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode(DEFAULT_ENCODING)


def from_base64str(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode(DEFAULT_ENCODING))


def relative_to_absolute_path(root_path: str, relative: str) -> str:
    return os.path.join(root_path, relative)


def absolute_to_relative_path(root_path: str, absolute: str) -> str:
    return absolute[len(root_path) :]
