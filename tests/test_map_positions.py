"""Stable dictionary positions preserve current values and checked missing keys."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_loads, json_string
def text(value: Json, key: str) -> str:
    return json_string(value[key])
def accumulate(rows: list[Json]) -> dict[str, int]:
    totals: dict[str, int] = {"a": 1}
    failures: int = 0
    for step in range(4):
        for row in rows:
            source: str = text(row, "from")
            target: str = text(row, "to")
            if source in totals:
                value: int = totals[source] + step + 1
                totals[target] = value
            if target not in totals:
                try:
                    print(totals[target])
                except Exception:
                    failures = failures + 1
    assert failures == 1
    return totals
def removing(rows: list[Json]) -> list[int]:
    totals: dict[str, int] = {"a": 1, "b": 2}
    observed: list[int] = []
    for step in range(3):
        for row in rows:
            key: str = text(row, "from")
            if key in totals:
                observed.append(totals[key])
        if step == 0:
            del totals["a"]
            totals["a"] = 9
    return observed
def clearing(rows: list[Json]) -> list[int]:
    totals: dict[str, int] = {"a": 1}
    observed: list[int] = []
    for step in range(3):
        for row in rows:
            key: str = text(row, "from")
            if key in totals:
                observed.append(totals[key])
        totals.clear()
        totals["a"] = step + 10
    return observed
def reassigned(rows: list[Json]) -> list[int]:
    totals: dict[str, int] = {"a": 1}
    observed: list[int] = []
    for step in range(3):
        for row in rows:
            key: str = text(row, "from")
            if key in totals:
                observed.append(totals[key])
        totals = {"a": step + 10}
    return observed
def check() -> None:
    rows: list[Json] = [json_loads('{"from":"b","to":"c"}'), json_loads('{"from":"a","to":"b"}')]
    result: dict[str, int] = accumulate(rows)
    assert result == {"a":1, "b":5, "c":8}
    inputs: list[Json] = [json_loads('{"from":"a"}'), json_loads('{"from":"b"}')]
    assert removing(inputs) == [1, 2, 9, 2, 9, 2]
    assert clearing(inputs) == [1, 10, 11]
    assert reassigned(inputs) == [1, 10, 11]
    print("stable map positions")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_map_positions(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert ("rt::cached_map_get" in generated) == optimize
    assert parity(tmp_path, SOURCE) == "stable map positions\n"
    return
