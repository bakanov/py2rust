"""Repeated immutable scans cache successful projections without eager validation."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_loads, json_string
def text(value: Json, key: str) -> str:
    return json_string(value[key])
def scan(rows: list[Json], rounds: int) -> list[str]:
    found: list[str] = []
    allowed: set[str] = {"世界", "second"}
    for step in range(rounds):
        for row in rows:
            name: str = text(row, "name")
            if name in allowed:
                found.append(name)
    return found
def lazy(rows: list[Json], rounds: int) -> int:
    errors: int = 0
    allowed: set[str] = {"yes"}
    for step in range(rounds):
        for row in rows:
            if step > 0:
                try:
                    if text(row, "missing") in allowed:
                        print("unexpected")
                except Exception:
                    errors = errors + 1
    return errors
def changing(rows: list[Json]) -> list[str]:
    found: list[str] = []
    for step in range(3):
        if step == 1:
            rows[0] = json_loads('{"name":"second"}')
        for row in rows:
            name: str = text(row, "name")
            found.append(name)
    return found
def rebound(batches: list[list[Json]]) -> list[str]:
    rows: list[Json] = [json_loads('{"name":"old"}')]
    found: list[str] = []
    for rows in batches:
        for row in rows:
            name: str = text(row, "name")
            found.append(name)
    return found
def check() -> None:
    rows: list[Json] = [json_loads('{"name":"世界"}'), json_loads('{"name":"second"}')]
    saved: list[str] = scan(rows, 3)
    assert saved == ["世界", "second", "世界", "second", "世界", "second"]
    rows[0] = json_loads('{"name":"changed"}')
    assert saved[0] == "世界"
    assert scan(rows, 1) == ["second"]
    assert lazy([json_loads('{}')], 0) == 0
    assert lazy([json_loads('{}')], 1) == 0
    assert lazy([json_loads('{}')], 3) == 2
    assert lazy([json_loads('{"missing":5}')], 3) == 2
    assert changing([json_loads('{"name":"first"}')]) == ["first", "second", "second"]
    batches: list[list[Json]] = [[json_loads('{"name":"a"}')], [json_loads('{"name":"b"}')]]
    assert rebound(batches) == ["a", "b"]
    print("lazy projection scans")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_repeated_projection_scans(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert ("rt::cached_json_string" in generated) == optimize
    assert parity(tmp_path, SOURCE) == "lazy projection scans\n"
    return
