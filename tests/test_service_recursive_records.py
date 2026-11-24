"""Self-recursive owned records through collections, including quoted project annotations."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import build, sources
from .test_services import parity, run


def test_recursive_record_collection_fields_and_traversal(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Node:
    number: int
    children: dict[str, "Node"]
    items: list["Node"]
    edges: tuple["Node", ...]
    wrapped: tuple[int, list["Node"]]
def leaf(number: int) -> "Node":
    return Node(number, {}, [], (), (0, []))
def total(node: "Node") -> int:
    result: int = node.number
    for name in node.children:
        result = result + total(node.children[name])
    for child in node.items:
        result = result + total(child)
    for child in node.edges:
        result = result + total(child)
    for child in node.wrapped[1]:
        result = result + total(child)
    return result
def chain(depth: int) -> "Node":
    result: Node = leaf(1)
    if depth > 0:
        result.children = {"next": chain(depth - 1)}
    return result
def check() -> None:
    tree: "Node" = Node(1, {"left": leaf(2), "right": leaf(3)}, [leaf(4)], (leaf(5),), (6, [leaf(7)]))
    assert total(tree) == 22
    children: dict[str, Node] = tree.children.copy()
    children["left"] = leaf(20)
    del children["right"]
    tree.children = children
    assert total(tree) == 37
    assert total(chain(96)) == 97
    print("recursive collection records")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_recursive_record_native_owned_copies(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Tree:
    text: str
    children: dict[str, "Tree"]
def check() -> None:
    first: Tree = Tree("root", {"a": Tree("leaf", {})})
    second: Tree = first
    children: dict[str, Tree] = second.children
    child: Tree = children["a"]
    child.text = "changed"
    children["a"] = child
    second.children = children
    assert first.children["a"].text == "leaf"
    assert second.children["a"].text == "changed"
    print("independent recursive copies")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "independent recursive copies\n", result.stderr
    return  # noqa: PLR1711


def test_quoted_record_project_aliases_and_literal_values(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "model.py": """from dataclasses import dataclass as record
@record
class Branch:
    label: str
    children: "dict[str, Branch]"
def make() -> "Branch":
    return Branch("Branch", {"x": Branch("Alias", {})})
""",
            "api.py": """from model import Branch as Alias, make
def inspect(value: "Alias") -> str:
    nested: "list[Alias]" = [value.children["x"]]
    return value.label + " " + nested[0].label
""",
            "main.py": """import model as trees
from api import inspect
def main() -> None:
    tree: "trees.Branch" = trees.make()
    assert inspect(tree) == "Branch Alias"
    print(inspect(tree))
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    binary = build(root, tmp_path / "rust")
    expected = subprocess.run([sys.executable, str(root / "main.py")], capture_output=True, text=True, check=True)
    result = subprocess.run(
        [str(binary)],
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == expected.stdout == "Branch Alias\n"
    generated = (tmp_path / "rust/src/main.rs").read_text()
    assert "children: indexmap::IndexMap<String, py__model__Branch>" in generated
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    ("annotation", "message"),
    [
        ('"Node"', "require list, dict or variadic tuple indirection"),
        ('tuple[int, "Node"]', "require list, dict or variadic tuple indirection"),
        ('tuple[tuple["Node", int], bool]', "require list, dict or variadic tuple indirection"),
        ('dict["Node", int]', "collection keys"),
        ('set["Node"]', "collection keys"),
        ('list["Missing"]', "unsupported or missing type annotation"),
        ('"Node | None"', "unsupported or missing type annotation"),
        ('"list["', "invalid quoted type annotation"),
    ],
)
def test_recursive_record_invalid_fields(annotation: str, message: str) -> None:
    source = (
        "from dataclasses import dataclass\n@dataclass\nclass Node:\n    field: "
        + annotation
        + '\ndef check() -> None:\n    return\nif __name__ == "__main__":\n    check()\n'
    )
    with pytest.raises(ServiceError, match=message):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711
