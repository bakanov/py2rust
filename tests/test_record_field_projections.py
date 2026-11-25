"""Owned field reads borrow ancestors, retaining independent final values."""

from pathlib import Path
import re

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity, run

SOURCE = """from dataclasses import dataclass
@dataclass
class Leaf:
    count: int
    text: str
    values: list[int]
@dataclass
class Root:
    leaf: Leaf
    children: dict[str, Leaf]
def make() -> Root:
    return Root(Leaf(3, "old", [1, 2]), {"a": Leaf(7, "child", [4])})
def inspect(root: Root) -> int:
    return root.leaf.count + root.children["a"].count
def temporary() -> str:
    return make().leaf.text
def check() -> None:
    root: Root = make()
    assert inspect(root) == 10
    assert root.leaf.text == "old"
    assert temporary() == "old"
    try:
        number: int = root.children["missing"].count
        assert False
    except Exception:
        print("missing child")
    print("projected fields")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_nested_field_projection(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
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
    match = re.search(r"fn \w*inspect\(.*?(?=\bfn |\Z)", generated, re.DOTALL)
    assert match is not None
    inspect = match.group()
    if optimize:
        assert ".clone()" not in inspect
    else:
        assert ".clone()" in inspect
    assert parity(tmp_path, SOURCE) == "missing child\nprojected fields\n"
    return


def test_projected_owned_field_keeps_value_semantics(tmp_path: Path) -> None:
    source = SOURCE[: SOURCE.index("def check()")] + """def check() -> None:
    root: Root = make()
    saved: list[int] = root.leaf.values
    saved.append(99)
    leaf: Leaf = root.children["a"]
    leaf.text = "changed"
    assert root.leaf.values == [1, 2]
    assert root.children["a"].text == "child"
    assert saved == [1, 2, 99]
    print("independent fields")
    return
if __name__ == "__main__":
    check()
"""
    # This subset deliberately uses independent owned values for these assignments.
    result = run(tmp_path, source, "rust")
    assert result.returncode == 0 and result.stdout == "independent fields\n", result.stderr
    return
