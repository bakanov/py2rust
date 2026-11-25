"""Dictionary byte lookups retain sparse keys, missing-key errors and mutation semantics."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """def sum_values(data: bytes, table: dict[int, int]) -> int:
    total: int = 0
    for byte in data:
        total = total + table[byte]
        for inner in b"a":
            total = total + table[inner]
        total = total + table[300]
        total = total + table[-1]
    return total

def check() -> None:
    table: dict[int, int] = {97: 2, 98: 3, 300: 5, -1: 7}
    assert sum_values(b"ab", table) == 33
    try:
        print(sum_values(b"z", table))
    except Exception:
        print("missing key")
    assert sum_values(b"", {}) == 0
    large: dict[int, int] = {}
    for value in range(400):
        large[value] = value
    large[-1] = 7
    assert sum_values(b"a", large) == 501
    for byte in b"aa":
        table[byte] = table[byte] + 1
    assert table[97] == 4
    print("integer views passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
def test_integer_lookup_views(tmp_path: Path, monkeypatch, frontend: str) -> None:
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    assert parity(tmp_path, SOURCE) == "missing key\ninteger views passed\n"
    assert "rt::IntLookup::new(" in (tmp_path / "rust/src/main.rs").read_text()
    return
