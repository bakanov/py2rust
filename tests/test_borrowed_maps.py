"""Write-only JSON maps materialize once and retain checked-error and snapshot semantics."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity, run

SOURCE = """from py2rust.stdlib import Json, json_loads, json_string, json_int
def text(value: Json, key: str) -> str:
    return json_string(value[key])
def build(rows: list[Json], rounds: int) -> tuple[dict[str, Json], dict[str, Json]]:
    result: dict[str, Json] = {}
    mirror: dict[str, Json] = {}
    for step in range(rounds):
        for row in rows:
            key: str = text(row, "id")
            result[key] = row
            mirror[key] = row
        if step == 2:
            break
    return (result, mirror)
def read_inside(rows: list[Json]) -> int:
    result: dict[str, Json] = {}
    total: int = 0
    for step in range(3):
        for row in rows:
            key: str = text(row, "id")
            result[key] = row
            total = total + json_int(result[key]["value"])
    return total
def caught(rows: list[Json]) -> int:
    result: dict[str, Json] = {}
    for step in range(1):
        try:
            for row in rows:
                result[text(row, "id")] = row
                assert False, "checked after insertion"
        except Exception:
            return json_int(result["a"]["value"])
    return -1
def changing(rows: list[Json]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for step in range(3):
        if step == 1:
            rows[0] = json_loads('{"id":"a","value":99}')
        for row in rows:
            result[text(row, "id")] = row
    return result
def seeded(rows: list[Json]) -> dict[str, Json]:
    result: dict[str, Json] = {"keep": json_loads('42')}
    for step in range(2):
        for row in rows:
            result[text(row, "id")] = row
    return result
def check() -> None:
    rows: list[Json] = [json_loads('{"id":"a","value":1}'), json_loads('{"id":"b","value":2}'), json_loads('{"id":"a","value":3}')]
    snapshots: tuple[dict[str, Json], dict[str, Json]] = build(rows, 10)
    assert list(snapshots[0]) == ["a", "b"]
    assert json_int(snapshots[0]["a"]["value"]) == 3
    assert snapshots[0] == snapshots[1]
    empty_map: dict[str, Json] = {}
    assert build(rows, 0) == (empty_map, empty_map)
    assert read_inside(rows) == 18
    assert caught(rows) == 1
    assert json_int(seeded(rows)["keep"]) == 42
    one: list[Json] = [json_loads('{"id":"a","value":1}')]
    assert json_int(changing(one)["a"]["value"]) == 99
    rows[0] = json_loads('{"id":"a","value":555}')
    assert json_int(snapshots[0]["a"]["value"]) == 3
    print("borrowed maps")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_borrowed_maps(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert ("__owned_map_" in generated) == optimize
    assert parity(tmp_path, SOURCE) == "borrowed maps\n"
    return


def test_materialized_maps_have_independent_values(tmp_path: Path) -> None:
    source = SOURCE[: SOURCE.index("def check()")] + """def check() -> None:
    rows: list[Json] = [json_loads('{"id":"a","value":1}')]
    pair: tuple[dict[str, Json], dict[str, Json]] = build(rows, 3)
    first: dict[str, Json] = pair[0]
    second: dict[str, Json] = pair[1]
    value: Json = first["a"]
    value["value"] = 99
    first["a"] = value
    assert json_int(first["a"]["value"]) == 99
    assert json_int(second["a"]["value"]) == 1
    assert json_int(rows[0]["value"]) == 1
    assert json_int(pair[0]["a"]["value"]) == 1
    print("independent materialized maps")
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0 and result.stdout == "independent materialized maps\n", result.stderr
    return
