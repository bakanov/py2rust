"""Execute assignment and deletion effects through the typed frontend."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service

from .test_services import run

SOURCE = """from py2rust.stdlib import Json, json_loads, json_int

def key() -> str:
    print("key")
    return "a"

def value() -> int:
    print("value")
    return 7

def json_value() -> Json:
    print("json value")
    return 8

def broken() -> int:
    print("broken")
    assert False, "replacement failed"
    return 0

def check() -> None:
    data: dict[str, int] = {"a": 1, "b": 2}
    data[key()] = value()
    assert data["a"] == 7
    try:
        data[key()] = broken()
    except Exception:
        print("caught replacement")
    assert data["a"] == 7
    del data[key()]
    data["a"] = 9
    assert list(data) == ["b", "a"]
    try:
        del data["missing"]
    except Exception:
        print("caught missing")
    document: Json = json_loads('{"a": 1}')
    document[key()] = json_value()
    assert json_int(document["a"]) == 8
    del document[key()]
    assert "a" not in document
    try:
        del document[key()]
    except Exception:
        print("caught JSON missing")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("optimize", [False, True])
def test_typed_mapping_update_and_delete(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    reference = run(tmp_path, SOURCE, "python")
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
    native = run(tmp_path, SOURCE, "rust")
    assert reference.returncode == native.returncode == 0, native.stderr
    assert reference.stderr == native.stderr == ""
    assert (
        reference.stdout.splitlines()
        == native.stdout.splitlines()
        == [
            "value",
            "key",
            "broken",
            "caught replacement",
            "key",
            "caught missing",
            "json value",
            "key",
            "key",
            "key",
            "caught JSON missing",
        ]
    )
    return
