"""Typed list insertion clamps indices after evaluating both arguments, preserving value semantics."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_insert_bounds_order_and_element_types(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import Json, pretty, FileHandle, file_open, file_write, file_seek, file_read
@dataclass
class Named:
    name: str
def index(value: int) -> int:
    print("index", value)
    return value
def element() -> str:
    print("element")
    return "世界"
def failure() -> str:
    assert False, "injected value failure"
    return ""
def check() -> None:
    for position in [-9223372036854775808, -10, -3, -2, -1, 0, 1, 2, 3, 10, 9223372036854775807]:
        values: list[str] = ["a", "b", "c"]
        values.insert(index(position), element())
        print(pretty(values))
        empty: list[int] = []
        empty.insert(position, 7)
        assert empty == [7]
    values: list[int] = [3, 1, 0]
    values.insert(values.pop(), values.pop())
    assert values == [1, 3]
    words: list[str] = ["one"]
    words.insert(0, words.pop())
    assert words == ["one"]
    caught: bool = False
    try:
        words.insert(index(99), failure())
    except Exception:
        caught = True
    assert caught and words == ["one"]
    objects: list[Json] = [{"a": 1}]
    objects.insert(0, None)
    assert len(objects) == 2 and objects[0] is None
    records: list[Named] = [Named("a")]
    records.insert(0, Named("b"))
    assert records[0].name == "b" and records[1].name == "a"
    with file_open("shared.bin", "w+b") as handle:
        handles: list[FileHandle] = []
        handles.insert(99, handle)
        file_write(handles[0], b"x")
        file_seek(handle, 0, 0)
        assert file_read(handle, 1) == b"x"
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.count("element\n") == 11 and "index 99\n" in output
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        'values.insert("0", 1)',
        "values.insert(True, 1)",
        'values.insert(0, "1")',
        "values.insert(0)",
        "values.insert(0, 1, 2)",
        "values.insert(index=0, object=1)",
    ],
)
def test_insert_rejects_unsupported_types_and_arguments(statement: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "def check() -> None:\n    values: list[int] = []\n    "
            + statement
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
