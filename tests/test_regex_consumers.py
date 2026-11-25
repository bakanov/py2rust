"""Capture field demand must preserve observable results and validation failures."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_string, json_keys, json_int, regex_capture

def group(value: Json, index: int) -> str:
    return json_string(value["groups"][index])

def escape(value: Json) -> Json:
    return value

def check() -> None:
    captured: Json = regex_capture("(é)(😀)?", "é", True)
    assert captured is not None
    assert group(captured, 1) == "é"
    assert captured["groups"][2] is None
    empty: Json = regex_capture("()", "", True)
    assert group(empty, 1) == ""
    absent: Json = regex_capture("(a)", "b", True)
    assert absent is None
    full: Json = regex_capture("(é)(😀)", "é😀", True)
    assert json_int(full["spans"][2][0]) == 1
    assert json_int(full["spans"][2][1]) == 2
    aliased: Json = regex_capture("(a)", "a", True)
    retained: Json = escape(aliased)
    assert json_keys(retained) == ["groups", "spans"]
    replaced: Json = regex_capture("(a)", "a", True)
    replaced = {"groups": ["changed"], "spans": []}
    assert group(replaced, 0) == "changed"
    for pattern in ["(", "()" * 65, "a" * 4097]:
        try:
            invalid: Json = regex_capture(pattern, "a", True)
            print(group(invalid, 0))
        except Exception:
            print("invalid pattern")
    try:
        too_long: Json = regex_capture("(.*)", "é" * 32769, True)
        print(group(too_long, 0))
    except Exception:
        print("input too long")
    print("capture consumers passed")
    return

if __name__ == "__main__":
    check()
"""

SOURCE = (
    SOURCE.replace('"()" * 65', repr("()" * 65))
    .replace('"a" * 4097', repr("a" * 4097))
    .replace('"é" * 32769', repr("é" * 32769))
)


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_capture_consumers(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    code = service.ServiceCompiler().compile(SOURCE)
    assert ("rt::regex_capture_groups(" in code) == optimize
    if optimize:
        assert code.count("rt::regex_capture_groups(") == 5
        assert code.count("rt::regex_capture(") == 3
    assert parity(tmp_path, SOURCE).endswith("capture consumers passed\n")
    return
