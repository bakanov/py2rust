"""Loop-scoped array views retain snapshots, validation and owned returns."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_array, json_int, json_loads

def inspect(document: Json) -> int:
    total: int = 0
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            numbers: list[Json] = json_array(atom["value"])
            total = total + json_int(numbers[0]) + json_int(numbers[-1])
    return total

def escaped(document: Json) -> list[Json]:
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            numbers: list[Json] = json_array(atom["value"])
            return numbers
    return []

def changed_item(document: Json) -> int:
    total: int = 0
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            numbers: list[Json] = json_array(atom["value"])
            atom["value"] = [99]
            total = total + json_int(numbers[0])
    return total

def changed_view(document: Json) -> int:
    total: int = 0
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            numbers: list[Json] = json_array(atom["value"])
            numbers.append(9)
            total = total + len(numbers) + len(json_array(atom["value"]))
    return total

def changed_parent(document: Json) -> int:
    total: int = 0
    for group in json_array(document["groups"]):
        for atom in json_array(group):
            numbers: list[Json] = json_array(atom["value"])
            document["groups"] = []
            total = total + json_int(numbers[0])
    return total

def check() -> None:
    payload: str = '{"groups":[[{"value":[1,2,3]},{"value":[4,5]}],[{"value":[6]}]]}'
    data: Json = json_loads(payload)
    assert inspect(data) == 25
    assert changed_item(json_loads(payload)) == 11
    assert changed_parent(json_loads(payload)) == 11
    assert changed_view(json_loads(payload)) == 15
    values: list[Json] = escaped(data)
    values.append(99)
    assert len(escaped(data)) == 3
    assert inspect(data) == 25
    for broken in ['[[{"value":false}]]', '[[{}]]', '[[{"value":[]}]]']:
        try:
            inspect(json_loads('{"groups":' + broken + '}'))
        except Exception:
            print("rejected")
    print("nested views passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_nested_views(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.views}
    for function in ["inspect", "escaped"]:
        assert set(plans[f"main.{function}"].bindings("array").values()) == {"document"}
    for function in ["changed_item", "changed_view", "changed_parent"]:
        assert plans[f"main.{function}"].views == ()
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
    assert (": &[rt::Json] = rt::json_array_ref" in generated) == (optimize and frontend == "typed")
    assert parity(tmp_path, SOURCE) == "rejected\nrejected\nrejected\nnested views passed\n"
    return
