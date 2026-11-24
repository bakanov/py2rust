"""Typed list concatenation preserves evaluation order and native ownership contracts."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


def test_list_concatenation_order_context_and_independent_containers(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import Json, json_equal
@dataclass
class Row:
    value: int
def left() -> list[int]:
    print("left")
    return [3, 1]
def right() -> list[int]:
    print("right")
    return [2, 1]
def check() -> None:
    values: list[int] = left() + right()
    assert values == [3, 1, 2, 1]
    empty: list[int] = [] + []
    assert len(empty) == 0
    copied: list[int] = [] + values + []
    copied.append(9)
    copied[0] = 7
    assert values == [3, 1, 2, 1] and copied == [7, 1, 2, 1, 9]
    rows: list[Row] = [Row(1)] + [Row(2)]
    assert rows[1].value == 2
    jsons: list[Json] = [{"x": 1}] + [None, [True]]
    assert json_equal(jsons, [{"x": 1}, None, [True]])
    assert [] + values == values
    other: list[int] = list() + values
    assert other == values
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output == "left\nright\n"
    return  # noqa: PLR1711


def test_list_concatenation_resource_handles_remain_shared(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from py2rust.stdlib import FileHandle, file_open, file_write, file_size
def check() -> None:
    with file_open("resource.bin", "w+b") as handle:
        original: list[FileHandle] = [handle]
        copied: list[FileHandle] = original + []
        file_write(copied[0], b"x")
        assert file_size(original[0]) == 1
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_list_concatenation_native_nested_values_are_owned(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    original: list[list[int]] = [[1]]
    copied: list[list[int]] = original + original
    copied[0].append(2)
    assert original[0] == [1] and copied[1] == [1]
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0, result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize("expression", ['[1] + ["x"]', "[1] + 1", "[1] - [2]", "[1] + (2,)", "[] + []"])
def test_list_concat_rejects_incompatible_or_untyped_operands(expression: str) -> None:
    with pytest.raises(ServiceError, match="expected Type|unsupported arithmetic|empty collection|collection shape"):
        ServiceCompiler().compile(
            "def check() -> None:\n    " + expression + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
