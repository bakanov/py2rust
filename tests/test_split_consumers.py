"""Temporary split fusion preserves Python values, errors and evaluation order."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """def source() -> str:
    print("source")
    return "a||b|"

def separator() -> str:
    print("separator")
    return "|"

def check() -> None:
    assert len(source().split(separator())) == 4
    assert source().split(separator())[1] == ""
    assert "aaa".split("aa")[-1] == "a"
    assert len("aaaaa".split("aa")) == 3
    assert len("a世界b世界".split("世界")) == 3
    assert len("a界b界".split("界")) == 3
    assert "aaaaa".split("aa")[-2] == ""
    assert "".split("|")[0] == ""
    assert len("".split()) == 0
    assert len(" a\\x1c世界\\x1f b ".split()) == 3
    assert " a\\x1c世界\\x1f b ".split()[1] == "世界"
    try:
        print(len("abc".split("")))
    except Exception:
        print("empty separator")
    try:
        print("".split()[0])
    except Exception:
        print("out of range")
    try:
        print("a".split("|")[-2])
    except Exception:
        print("negative out of range")
    text: str = "a|bb|ccc"
    total: int = 0
    saved: list[str] = []
    for word in text.split("|"):
        text = "changed"
        saved.append(word)
        total = total + len(word)
    assert total == 6
    assert saved == ["a", "bb", "ccc"]
    for word in " a  b ".split():
        word = word + "!"
        assert word.endswith("!")
    try:
        for word in "abc".split(""):
            print("must not execute")
    except Exception:
        print("loop separator")
    for outer in "a|b".split("|"):
        for inner in "x|y".split("|"):
            assert len(outer) + len(inner) == 2
    print("split consumers passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_split_consumers(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    result = parity(tmp_path, SOURCE)
    assert result.endswith("loop separator\nsplit consumers passed\n")


def test_temporary_lists_removed_but_stored_lists_preserved(tmp_path: Path) -> None:
    source = """def check(text: str) -> int:
    stored: list[str] = text.split("|")
    prefix: str = text.split("|")[0]
    total: int = len(text.split("|"))
    for part in text.split("|"):
        total = total + len(part)
    return len(stored) + len(prefix) + total
"""
    code = pipeline.compile_typed({"main": (tmp_path / "main.py", source)})
    assert "rt::split_item(" in code
    assert "rt::str_split_count(" in code
    assert "rt::str_split(" in code  # The explicitly retained list still owns its values.
    assert "let __split_source" in code
    assert '"|".to_string()' not in code


def test_split_selection_in_json_tail_return(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    source = """from py2rust.stdlib import Json, json_string

def document() -> Json:
    target: str = "/notes?limit=20"
    return {"route": target.split("?")[0], "last": target.split("?")[-1]}

if __name__ == "__main__":
    value: Json = document()
    assert json_string(value["route"]) == "/notes"
    assert json_string(value["last"]) == "limit=20"
    print("tail split passed")
"""
    assert parity(tmp_path, source) == "tail split passed\n"
