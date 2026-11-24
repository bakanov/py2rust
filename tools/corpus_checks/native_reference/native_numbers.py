"""Independent CPython adapter model; never packaged into the native application."""


def checked(value: int) -> int:
    if not -(2**63) <= value < 2**63:
        raise ValueError("out of range integral type conversion attempted")
    return value


def narrow(value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError("out of range integral type conversion attempted")
    return value


def unsigned_result(value: int) -> int:
    return checked(2**64 - 1 if value < 0 else value)


def double_width(value: int) -> int:
    return checked(value * 2)


def checked_add(left: int, right: int) -> int:
    total = left + right
    if not -(2**63) <= total < 2**63:
        raise ValueError("native integer overflow")
    return total


def invert(value: bool) -> bool:
    return not value
