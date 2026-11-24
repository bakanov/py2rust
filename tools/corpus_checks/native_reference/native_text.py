"""Reference fixture for UTF-8, owned tuples, byte buffers and fallible text."""


def inspect(value: str) -> tuple[int, int, str]:
    return len(value), len(value.encode()), value[::-1]


def transform(value: bytes) -> tuple[bytes, int]:
    return bytes(byte ^ 0xA5 for byte in reversed(value)), len(value)


def accept(value: str) -> str:
    if value == "deny":
        raise ValueError("native rejected text")
    return "accepted:" + value


def unit(_value: str) -> None:
    return None
