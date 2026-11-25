"""Executable parity for JSON projections and borrowed serialization sources."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import Json, json_array, json_keys, json_dumps
from dataclasses import dataclass

@dataclass
class Record:
    values: list[int]

def key() -> str:
    print("key first")
    return "世界"

def object_value() -> Json:
    print("object second")
    return {"世界": [1, 2], "other": None}

def encode(value: Json) -> str:
    return json_dumps(value)

def table(selector: str) -> str:
    lookup: dict[str, str] = {"a": "one", "b": "two", "c": "three", "d": "four"}
    return lookup[selector]

def fresh() -> dict[str, int]:
    lookup: dict[str, int] = {"a": 1, "b": 2, "c": 3, "d": 4}
    return lookup

def mutable() -> int:
    lookup: dict[str, int] = {"a": 1, "b": 2, "c": 3, "d": 4}
    lookup["a"] = lookup["a"] + 1
    return lookup["a"]

def check() -> None:
    assert table("a") == "one" and table("b") == "two"
    first: dict[str, int] = fresh()
    first["a"] = 100
    assert fresh()["a"] == 1
    assert mutable() == 2 and mutable() == 2
    assert key() in json_keys(object_value())
    assert "missing" not in json_keys(object_value())
    assert len(json_keys(object_value())) == 2
    assert len(json_keys(object_value())) < 3
    assert len(json_array(object_value()["世界"])) < 3
    assert len(json_array(object_value()["世界"])) == 2
    value: Json = {"nested": {"世界": []}}
    assert "世界" in json_keys(value["nested"])
    assert len(json_keys(value["nested"])) == 1
    assert len(json_array(value["nested"]["世界"])) == 0
    keys: list[str] = json_keys(value)
    value["later"] = 3
    assert keys == ["nested"]
    invalid: Json = ["世界"]
    try:
        print(key() in json_keys(invalid))
    except Exception:
        print("not an object")
    try:
        print(len(json_keys(invalid)))
    except Exception:
        print("invalid key count")
    try:
        print(len(json_array(value)))
    except Exception:
        print("not an array")
    records: list[Record] = [Record([1, 2]), Record([3])]
    print(encode(records[0].values))
    print(encode(records[1].values))
    mapping: dict[str, list[int]] = {"a": [4, 5]}
    print(encode(mapping))
    print(encode(mapping["a"]))
    print(encode([1.5, 2.5]))
    rows: list[Json] = [{"x": [1, 2]}, {"x": []}]
    print(encode(rows))
    assert len(rows) == 2
    print(encode(rows))
    deep: Json = 0
    for level in range(64):
        deep = [deep]
    deep_rows: list[Json] = [deep]
    try:
        print(encode(deep_rows))
    except Exception:
        print("depth limit")
    print("consumers passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_json_consumers(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert parity(tmp_path, SOURCE).endswith("consumers passed\n")
    return


def test_projected_string_comparison(tmp_path: Path, monkeypatch) -> None:
    source = """from dataclasses import dataclass

@dataclass
class Row:
    label: str

def right() -> str:
    print("right")
    return "世界"

def check() -> None:
    rows: list[str] = ["世界", "a", "😀"]
    other: list[str] = ["世界", "b", "😀"]
    total: int = 0
    for i in range(len(rows)):
        for j in range(len(other)):
            if rows[i] == other[j]:
                total = total + 1
    assert total == 2
    assert rows[-1] >= other[0]
    record: Row = Row("世界")
    assert record.label == rows[0]
    assert rows[0] == right()
    assert rows[0] != rows.pop()
    try:
        print(rows[99] == right())
    except Exception:
        print("left failed first")
    print("projected comparisons passed")
    return

if __name__ == "__main__":
    check()
"""
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, text: pipeline.compile_typed({"main": (tmp_path / "main.py", text)}),
    )
    assert parity(tmp_path, source) == "right\nleft failed first\nprojected comparisons passed\n"
    return
