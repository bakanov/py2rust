"""Borrow pure checked string projections only at stable read-only consumers."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_loads, json_string

def text(value: Json, key: str) -> str:
    return json_string(value[key])

def noisy(value: Json, key: str) -> str:
    print("helper effect")
    return json_string(value[key])

def source() -> Json:
    print("source effect")
    return json_loads('{"name":"世界"}')

def container(value: Json) -> set[str]:
    print("container effect")
    value["name"] = "changed"
    return {"世界"}

def inspect(value: Json, key: str, allowed: set[str], counts: dict[str, int]) -> bool:
    return text(value, key) in allowed and text(value, "name") in counts

def borrowed_local(value: Json) -> str:
    name: str = text(value, "name")
    allowed: set[str] = set()
    allowed.add(name)
    allowed.add(text(value, "name"))
    assert name in allowed and len(allowed) == 1
    return name

def changed_backing(value: Json) -> str:
    name: str = text(value, "name")
    value["name"] = "changed"
    return name

def owned(value: Json) -> str:
    return text(value, "name")

def check() -> None:
    value: Json = json_loads('{"name":"世界"}')
    assert inspect(value, "name", {"世界"}, {"世界": 1})
    assert text(value, "name") not in {"absent"}
    assert noisy(value, "name") in {"世界"}
    assert text(source(), "name") in {"世界"}
    assert text(value, "name") in container(value)
    value = json_loads('{"name":"世界"}')
    assert borrowed_local(value) == "世界"
    assert changed_backing(value) == "世界"
    value = json_loads('{"name":"世界"}')
    saved: str = owned(value)
    value["name"] = "new"
    assert saved == "世界"
    for raw in ['{}', '{"name":2}']:
        try:
            assert text(json_loads(raw), "name") in {"世界"}
        except Exception:
            print("checked temporary error")
        invalid: Json = json_loads(raw)
        try:
            assert inspect(invalid, "name", {"世界"}, {"世界": 1})
        except Exception:
            print("checked borrowed error")
    print("projected strings")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_projected_string_membership(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    generated = service.ServiceCompiler().compile(SOURCE)
    assert ("rt::json_string_ref(rt::json_key_ref" in generated) == optimize
    # The mutating callee receives an owned value in Rust's subset. Do not inspect
    # its caller's post-call JSON here; the test checks left-before-right ordering.
    result = parity(tmp_path, SOURCE)
    assert (
        result
        == "helper effect\nsource effect\ncontainer effect\nchecked temporary error\nchecked borrowed error\nchecked temporary error\nchecked borrowed error\nprojected strings\n"
    )
    return
