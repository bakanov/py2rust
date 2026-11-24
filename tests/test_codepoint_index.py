"""Numeric-only Unicode indexing selects a cache without changing evaluation semantics."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import ast
from pathlib import Path

from py2rust.compiler.optimization import text_accesses
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity

SOURCE = """
def checksum(text: str, positions: list[int]) -> int:
    total: int = 0
    for position in positions:
        total = total + ord(text[position])
    return total + len(text)

def check() -> None:
    assert checksum("é🙂a", [0, 1, 2, -1, -2, -3]) == 257819
    assert checksum("abc", [0, -1]) == 199
    assert checksum("", []) == 0
    for position in [-9223372036854775808, -4, 3, 9223372036854775807]:
        caught: bool = False
        try:
            print(checksum("é🙂a", [position]))
        except Exception:
            caught = True
        assert caught
    print("codepoint cache semantics passed")
    return

if __name__ == "__main__":
    check()
"""


def test_codepoint_cache_semantics(tmp_path: Path) -> None:
    output = ServiceCompiler().compile(SOURCE)
    assert "rt::CodepointIndex" in output
    parity(tmp_path, SOURCE)
    return


def test_codepoint_cache_selection_is_conservative() -> None:
    function = ast.parse(SOURCE).body[0]
    assert text_accesses(function, {"text"}, builtin_ord=True)["text"].representation == "CodepointIndex"
    assert text_accesses(function, {"text"}, builtin_ord=False)["text"].representation == "TextIndex"
    for expression in ["text[position]", "ord(text[position:position + 1])", "ord(text[next_index()])"]:
        mixed = ast.parse(
            "def f(text, positions):\n    for position in positions:\n        ord(text[position])\n        "
            + expression
        ).body[0]
        assert text_accesses(mixed, {"text"}, builtin_ord=True)["text"].representation == "TextIndex"
    return
