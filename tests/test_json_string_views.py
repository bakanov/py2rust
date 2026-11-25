"""Borrow JSON text only while its complete backing remains stable."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_array, json_loads, json_string, parallel_map

def inspect(document: Json) -> list[str]:
    result: list[str] = []
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            text: str = json_string(atom["text"])
            assert text.startswith("h")
            result.append(text)
            result.append(text.upper())
    return result

def direct(document: Json) -> str:
    text: str = json_string(document["text"])
    return text

def snapshot(document: Json) -> str:
    text: str = json_string(document["text"])
    document["text"] = "new"
    return text

def rebound(document: Json) -> str:
    text: str = json_string(document["text"])
    text = text + "!"
    return text

def consume(document: Json) -> int:
    document["text"] = "changed"
    return 1

def callback(document: Json) -> Json:
    text: str = json_string(document["text"])
    assert consume(document) == 1
    return text

def check() -> None:
    assert inspect(json_loads('{"groups":[[{"text":"héllo"}],[{"text":"hi"}]]}')) == ["héllo", "HÉLLO", "hi", "HI"]
    assert direct(json_loads('{"text":"世界"}')) == "世界"
    assert snapshot(json_loads('{"text":"old"}')) == "old"
    assert rebound(json_loads('{"text":"old"}')) == "old!"
    for invalid in ['{"text":false}', '{}']:
        try:
            direct(json_loads(invalid))
        except Exception:
            print("rejected")
    assert json_string(parallel_map(callback, [json_loads('{"text":"old"}')], 2)[0]) == "old"
    print("text views passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_json_string_views(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.views}
    for name in ["inspect", "direct", "callback"]:
        assert set(plans[f"main.{name}"].bindings("json_text").values()) == {"document"}
    for name in ["snapshot", "rebound"]:
        assert plans[f"main.{name}"].views == ()
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
    assert generated.count("rt::json_string_ref") == (3 if optimize and frontend == "typed" else 0)
    assert parity(tmp_path, SOURCE) == "rejected\nrejected\ntext views passed\n"
    return
