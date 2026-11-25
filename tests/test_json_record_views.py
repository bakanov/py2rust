"""Nonescaping JSON records may borrow fields; escaping/mutable records remain owned."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_keys, json_dumps

def label(value: str) -> str:
    print(value)
    return value

def collect(source: Json, names: list[str]) -> Json:
    requests: list[Json] = [{"tag": "root", "data": source}]
    for name in names:
        requests.append({"tag": label(name), "data": source["children"][name]})
    result: list[Json] = []
    for request in requests:
        result.append({"tag": request["tag"], "count": len(json_keys(request["data"]))})
    return result

def escaped(source: Json) -> list[Json]:
    requests: list[Json] = [{"tag": "root", "data": source}]
    for request in requests:
        print(len(json_keys(request["data"])))
    return requests

def mutated(source: Json) -> Json:
    requests: list[Json] = [{"tag": "root", "data": source}]
    for request in requests:
        request["tag"] = "changed"
        return request
    return None

def mixed(source: Json) -> Json:
    requests: list[Json] = [{"tag": "root", "data": source}]
    requests.append({"tag": 42, "data": source})
    result: list[Json] = []
    for request in requests:
        result.append(request["tag"])
    return result

def reordered(source: Json) -> Json:
    requests: list[Json] = [{"tag": "root", "data": source}]
    requests.append({"data": source, "tag": "next"})
    result: list[Json] = []
    for request in requests:
        result.append(request["tag"])
    return result

def check() -> None:
    source: Json = {"children": {"a": {"x": 1}, "b": {"x": 2, "y": 3}}}
    print(json_dumps(collect(source, ["a", "b"])))
    try:
        print(json_dumps(collect(source, ["missing"])))
    except Exception:
        print("missing after label")
    print(json_dumps(escaped(source)))
    print(json_dumps(mutated(source)))
    print(json_dumps(mixed(source)))
    print(json_dumps(reordered(source)))
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("optimize", [False, True])
def test_record_views(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
    )
    output = parity(tmp_path, SOURCE)
    assert "missing\nmissing after label" in output
    code = (tmp_path / "rust/src/main.rs").read_text()
    assert ("Vec<(String,&rt::Json" in code.replace(" ", "")) == optimize
    return


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
def test_internal_view_type_does_not_reserve_python_name(tmp_path: Path, monkeypatch, frontend: str) -> None:
    source = """from dataclasses import dataclass

@dataclass
class _json_ref:
    value: int

def make() -> _json_ref:
    return _json_ref(42)

if __name__ == "__main__":
    print(make().value)
"""
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
        )
    assert parity(tmp_path, source) == "42\n"
    return
