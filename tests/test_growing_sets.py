"""Positive membership caches preserve growing-set behavior and lazy checked errors."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_loads, json_string
def text(value: Json, key: str) -> str:
    return json_string(value[key])
def closure(rows: list[Json]) -> tuple[set[str], int, int]:
    seen: set[str] = {"a"}
    visits: int = 0
    misses: int = 0
    for step in range(4):
        for row in rows:
            target: str = text(row, "to")
            if text(row, "from") in seen:
                visits = visits + 1
                seen.add(target)
            if target not in seen:
                misses = misses + 1
    return (seen, visits, misses)
def clearing(rows: list[Json]) -> int:
    seen: set[str] = {"a"}
    visits: int = 0
    for step in range(3):
        for row in rows:
            if text(row, "from") in seen:
                visits = visits + 1
        seen.clear()
        if step == 1:
            seen.add("a")
    return visits
def rebound(rows: list[Json]) -> int:
    seen: set[str] = {"a"}
    visits: int = 0
    for step in range(3):
        for row in rows:
            if text(row, "from") in seen:
                visits = visits + 1
        seen = set()
        if step == 1:
            seen.add("a")
    return visits
def lazy(rows: list[Json], rounds: int) -> int:
    seen: set[str] = {"a"}
    failures: int = 0
    for step in range(rounds):
        for row in rows:
            if text(row, "from") in seen:
                try:
                    seen.add(text(row, "missing"))
                except Exception:
                    failures = failures + 1
    return failures
def check() -> None:
    rows: list[Json] = [json_loads('{"from":"b","to":"c"}'), json_loads('{"from":"a","to":"b"}'), json_loads('{"from":"d","to":"e"}'), json_loads('{"from":"c","to":"d"}')]
    assert closure(rows) == ({"a", "b", "c", "d", "e"}, 12, 4)
    inputs: list[Json] = [json_loads('{"from":"a"}')]
    assert clearing(inputs) == 2
    assert rebound(inputs) == 2
    assert lazy(inputs, 0) == 0
    assert lazy(inputs, 3) == 3
    assert lazy([json_loads('{"from":"a","missing":42}')], 3) == 3
    assert lazy([json_loads('{"from":"absent"}')], 3) == 0
    print("growing sets")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_growing_sets(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert ("__set_membership_" in generated) == optimize
    assert parity(tmp_path, SOURCE) == "growing sets\n"
    return
