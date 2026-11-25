"""Recursive read-only traversal borrows ancestors and materializes owned escapes."""

from pathlib import Path
import re

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity, run

SOURCE = """from dataclasses import dataclass
@dataclass
class Node:
    value: int
    children: dict[str, "Node"]
def leaf(value: int) -> Node:
    return Node(value, {})
def find(root: Node, path: list[str]) -> Node:
    cursor: Node = root
    for key in path:
        if key not in cursor.children:
            return leaf(-1)
        cursor = cursor.children[key]
    return cursor
def snapshots(root: Node, path: list[str]) -> list[Node]:
    cursor: Node = root
    result: list[Node] = [cursor]
    for key in path:
        cursor = cursor.children[key]
        result.append(cursor)
    return result
def checked(root: Node) -> int:
    cursor: Node = root
    try:
        cursor = cursor.children["missing"]
    except Exception:
        return cursor.value
    return -1
def check() -> None:
    root: Node = Node(1, {"a": Node(2, {"世界": leaf(3)})})
    assert find(root, ["a", "世界"]).value == 3
    assert find(root, []).value == 1
    assert find(root, ["missing"]).value == -1
    records: list[Node] = snapshots(root, ["a", "世界"])
    assert records[0].value == 1 and records[1].value == 2 and records[2].value == 3
    assert checked(root) == 1
    print("record cursors")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_record_cursor_traversal(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert bool(re.search(r"let mut cursor\w*: &", generated)) == optimize
    assert parity(tmp_path, SOURCE) == "record cursors\n"
    return


def test_record_cursor_owned_results_and_mutation_fallback(tmp_path: Path) -> None:
    source = SOURCE[: SOURCE.index("def check()")] + """def modify(root: Node) -> Node:
    cursor: Node = root
    cursor = cursor.children["a"]
    cursor.value = 99
    return cursor
def method(root: Node) -> Node:
    cursor: Node = root
    cursor = cursor.children["a"]
    children: dict[str, Node] = cursor.children.copy()
    children.clear()
    cursor.children = children
    return cursor
def check() -> None:
    root: Node = Node(1, {"a": Node(2, {"世界": leaf(3)})})
    saved: Node = find(root, ["a"])
    saved.value = 8
    assert root.children["a"].value == 2
    assert modify(root).value == 99
    assert root.children["a"].value == 2
    assert len(method(root).children) == 0
    assert len(root.children["a"].children) == 1
    print("independent cursor results")
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0 and result.stdout == "independent cursor results\n", result.stderr
    return
