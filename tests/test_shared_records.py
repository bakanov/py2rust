"""Recursive snapshots retain value semantics with copy-on-write storage."""

from pathlib import Path
import re

import pytest

from py2rust.compiler import pipeline, service
from .test_services import run

SOURCE = """from dataclasses import dataclass
@dataclass
class NodeStorage:
    number: int
@dataclass
class Node:
    number: int
    children: dict[str, "Node"]
def rewrite(node: Node) -> Node:
    children: dict[str, Node] = node.children
    before: int = len(node.children)
    children["new"] = Node(7, {})
    node.children = children
    assert len(node.children) == before + 1
    return node
def fail(node: Node) -> Node:
    node.number = 999
    assert False, "failed update"
    return node
def check() -> None:
    original: Node = Node(1, {"a": Node(2, {"b": Node(3, {})})})
    snapshot: Node = original
    history: list[Node] = [original]
    changed: Node = original
    changed.number = changed.number + 10
    children: dict[str, Node] = changed.children
    child: Node = children["a"]
    child.number = 22
    grandchildren: dict[str, Node] = child.children
    grandchild: Node = grandchildren["b"]
    grandchild.number = 33
    grandchildren["b"] = grandchild
    child.children = grandchildren
    children["a"] = child
    changed.children = children
    changed = rewrite(changed)
    assert changed.number == 11
    assert changed.children["a"].number == 22
    assert changed.children["a"].children["b"].number == 33
    assert len(changed.children) == 2
    assert original.number == 1 and snapshot.number == 1
    assert history[0].children["a"].children["b"].number == 3
    assert original.children["a"].number == 2
    assert len(original.children) == 1
    try:
        original = fail(original)
    except Exception:
        assert original.number == 1
    marker: NodeStorage = NodeStorage(9)
    assert marker.number == 9
    print("independent recursive snapshots")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_shared_recursive_snapshots(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    assert ("std::sync::Arc::make_mut" in generated) == optimize
    assert re.search(r"struct \w*NodeStorage \{", generated)
    result = run(tmp_path, SOURCE, "rust")
    assert result.returncode == 0 and result.stdout == "independent recursive snapshots\n", result.stderr
    return


def test_resource_records_keep_owned_storage() -> None:
    source = """from dataclasses import dataclass
from py2rust.stdlib import FileHandle
@dataclass
class Node:
    handle: FileHandle
    children: list["Node"]
def check() -> None:
    return
if __name__ == "__main__":
    check()
"""
    generated = service.ServiceCompiler().compile(source)
    assert "std::sync::Arc" not in generated
    assert "struct Node {" in generated
    return
