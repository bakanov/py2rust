"""Large Unicode access preserves values, bounds and ownership boundaries."""

# ruff: noqa: EXE002, PLR1711 - exFAT and explicit-return convention
from pathlib import Path

from py2rust.compiler.service import ServiceCompiler

from .test_services import parity

SOURCE = """
def read(character: str) -> int:
    return ord(character)

def scan(text: str, positions: list[int]) -> int:
    total: int = 0
    for position in positions:
        total = total + read(text[position])
        total = total + ord(text[position])
    return total

def owned(text: str, position: int) -> str:
    return text[position]

def check() -> None:
    text: str = ""
    for i in range(22000):
        text = text + "é🙂a"
    positions: list[int] = []
    expected: int = 0
    for i in range(256):
        position: int = (i * 7919) % 66000
        positions.append(position)
        positions.append(position - 66000)
        expected = expected + ord("é🙂a"[position % 3]) * 4
    assert scan(text, positions) == expected
    assert owned(text, -2) == "🙂"
    assert owned(text, 0) == "é"
    before: str = text
    character: str = text[1]
    text = "changed"
    assert character == "🙂" and len(before) == 66000
    for bound in [-9223372036854775808, -66001, 66000, 9223372036854775807]:
        caught: bool = False
        try:
            print(read(before[bound]))
        except Exception:
            caught = True
        assert caught
    print("large Unicode views passed")
    return

if __name__ == "__main__":
    check()
"""


def test_large_unicode_views(tmp_path: Path) -> None:
    parity(tmp_path, SOURCE)
    return


def test_character_views_only_at_read_boundaries() -> None:
    output = ServiceCompiler().compile(SOURCE)
    assert ".at_view(" in output
    assert ".codepoint(" in output
    assert "rt::char_at(" in output  # owned return remains independent
    compiler = ServiceCompiler()
    compiler.optimize_text = False
    conservative = compiler.compile(SOURCE)
    assert ".at_view(" not in conservative
    assert "rt::char_at_view(" not in conservative
    return
