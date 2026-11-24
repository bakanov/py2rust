"""Probe indexed Unicode access with sequential, reverse and permuted positions.

The benchmark driver constructs text/positions outside the measured call. Keeping
positions explicit prevents a sequential-only implementation from hiding random
access costs. This kernel is compiled as a complete standalone application.
"""

# ruff: noqa: EXE002 - exFAT executable modes


def checksum(text: str, positions: list[int]) -> int:
    result: int = 0
    for position in positions:
        result = result + ord(text[position])
    return result


if __name__ == "__main__":
    assert checksum("é🙂a", [0, 1, 2]) == 128908
    assert checksum("é🙂a", [2, 0, -2]) == 128908
