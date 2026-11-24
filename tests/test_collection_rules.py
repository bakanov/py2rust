"""Collection rules preserve effects even when the result is statically known."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import parity

SOURCE = """def pair() -> tuple[int, str]:
    print("pair evaluated")
    return (1, "text")

def failed_pair() -> tuple[int, str]:
    assert False, "expected failure"
    return (0, "")

def check() -> None:
    assert len(pair()) == 2
    try:
        len(failed_pair())
    except Exception:
        print("caught call")
    pairs: list[tuple[int, str]] = [(1, "value")]
    try:
        len(pairs[2])
    except Exception:
        print("caught index")
    assert len("é😀") == 2
    assert len("é😀".encode()) == 6
    assert list(bytes([0, 128, 255])) == [0, 128, 255]
    original: list[int] = [1, 2]
    snapshot: list[int] = list(original)
    original.append(3)
    assert snapshot == [1, 2]
    mapping: dict[str, int] = {"b": 2, "a": 1}
    assert list(mapping) == ["b", "a"]
    assert list((4, 5)) == [4, 5]
    assert tuple(original) == (1, 2, 3)
    print("collections passed")

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("optimize", [False, True])
def test_collection_rules_execute(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == "pair evaluated\ncaught call\ncaught index\ncollections passed\n"
    return
