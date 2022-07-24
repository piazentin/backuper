import base64

DEFAULT_ENCODING = 'UTF-8'


def to_base64str(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode(DEFAULT_ENCODING)


def from_base64str(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode(DEFAULT_ENCODING))
