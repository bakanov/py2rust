"""String-chain fusion retains value snapshots and left-to-right failures."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_loads

def value(label: str) -> str:
    print(label)
    return label

def check() -> None:
    words: list[str] = ["first", "last"]
    combined: str = words[0] + ":" + words.pop() + ":" + value("世界")
    assert combined == "first:last:世界"
    assert words == ["first"]
    print(value("a") + (value("b") + value("c")))
    try:
        print(words[99] + value("must not run") + "end")
    except Exception:
        print("left failed first")
    assert ([1] + []) == [1]
    assert 1 + 2 + 3 == 6
    document: Json = json_loads('{"rows": [null, {"nested": [1, 2]}]}')
    assert document is not None
    assert None is not document
    assert document["rows"][0] is None
    assert None is document["rows"][0]
    assert document["rows"][1] is not None
    try:
        print(document["absent"] is None)
    except Exception:
        print("missing key")
    print("fusion passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_string_chains(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    output = parity(tmp_path, SOURCE)
    assert "must not run" not in output
    assert output.endswith("fusion passed\n")
    return
