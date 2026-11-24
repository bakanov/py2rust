"""Stable cached sort keys, callback order, whole-project linkage and diagnostic boundaries."""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_project import build, sources
from .test_services import parity, run


def test_sort_keys_records_stable_reverse_and_argument_order(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Row:
    group: str
    number: int
def values() -> list[Row]:
    print("values")
    return [Row("b", 0), Row("a", 1), Row("b", 2), Row("a", 3)]
def descending() -> bool:
    print("reverse")
    return True
def rank(row: Row) -> str:
    print(row.number)
    return row.group
def forbidden(row: Row) -> int:
    assert False, "empty list called its key"
    return 0
def check() -> None:
    ordered: list[Row] = sorted(values(), reverse=descending(), key=rank)
    ids: list[int] = []
    for row in ordered:
        ids.append(row.number)
    assert ids == [0, 2, 1, 3]
    source: list[Row] = values()
    ordered = sorted(source, key=rank, reverse=False)
    ids.clear()
    for row in ordered:
        ids.append(row.number)
    assert ids == [1, 3, 0, 2] and source[0].number == 0
    empty: list[Row] = sorted([], key=forbidden)
    assert len(empty) == 0 and len(sorted([], key=forbidden)) == 0
    assert sorted([3, 1, 2], key=None, reverse=True) == [3, 2, 1]
    assert sorted([3, 1, 2], reverse=False) == [1, 2, 3]
    assert sorted([3, 1, 2], key=None) == [1, 2, 3]
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["values", "reverse", "0", "1", "2", "3", "values", "0", "1", "2", "3"]
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_sort_keys_against_independent_generated_oracle(tmp_path: Path, engine: str) -> None:
    rng = random.Random(570057)
    batches = [[], [("same", 0, {"id": 0}), ("same", 0, {"id": 1})]]
    for count in range(42):
        batches.append(
            [
                (
                    rng.choice(["", "a", "é", "世界", "😀"]),
                    rng.randrange(-3, 4),
                    {"id": i, "payload": [None, True, "x"]},
                )
                for i in range(count * 3)
            ]
        )
    expected = [
        [sorted(rows, key=lambda row: (row[0], row[1]), reverse=reverse) for reverse in [False, True]]
        for rows in batches
    ]
    source = """
from py2rust.stdlib import Json, json_dumps, json_loads, json_array, json_string, json_int, read_text
def rank(row: tuple[str, int, Json]) -> tuple[str, int]:
    return (row[0], row[1])
def check() -> None:
    batches: list[list[tuple[str, int, Json]]] = []
    for raw_batch in json_array(json_loads(read_text("batches.json"))):
        rows: list[tuple[str, int, Json]] = []
        for raw_row in json_array(raw_batch):
            rows.append((json_string(raw_row[0]), json_int(raw_row[1]), raw_row[2]))
        batches.append(rows)
    results: list[Json] = []
    for batch in batches:
        directions: list[Json] = []
        for direction in [False, True]:
            ordered: list[tuple[str, int, Json]] = sorted(batch, key=rank, reverse=direction)
            directions.append(ordered)
        results.append(directions)
    print(json_dumps(results))
    return
if __name__ == "__main__":
    check()
"""
    (tmp_path / "batches.json").write_text(json.dumps(batches, ensure_ascii=False))
    actual = run(tmp_path, source, engine)
    assert actual.returncode == 0, actual.stderr
    assert json.loads(actual.stdout) == json.loads(json.dumps(expected))
    return  # noqa: PLR1711


def test_sort_key_failures_stop_evaluation_without_reordering_input(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def rank(value: int) -> int:
    print(value)
    assert value != 2, "bad key"
    return -value
def reverse_failure() -> bool:
    print("reverse failure")
    assert False, "bad reverse"
    return False
def check() -> None:
    original: list[int] = [3, 2, 1]
    errors: int = 0
    try:
        copied: list[int] = sorted(original, key=rank)
    except Exception as error:
        print(str(error))
        errors = errors + 1
    assert original == [3, 2, 1]
    try:
        copied: list[int] = sorted(original, key=rank, reverse=reverse_failure())
    except Exception as error:
        print(str(error))
        errors = errors + 1
    assert errors == 2 and original == [3, 2, 1]
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["3", "2", "bad key", "reverse failure", "bad reverse"]
    return  # noqa: PLR1711


def test_sort_keys_keep_native_owned_record_arguments(tmp_path: Path) -> None:
    result = run(
        tmp_path,
        """
from dataclasses import dataclass
@dataclass
class Row:
    value: int
def mutate(row: Row) -> int:
    previous: int = row.value
    row.value = 100
    return previous
def check() -> None:
    source: list[Row] = [Row(2), Row(1)]
    ordered: list[Row] = sorted(source, key=mutate)
    assert source[0].value == 2 and source[1].value == 1
    assert ordered[0].value == 1 and ordered[1].value == 2
    first: Row = ordered[0]
    first.value = 99
    ordered[0] = first
    assert source[1].value == 1
    print("owned sort arguments")
    return
if __name__ == "__main__":
    check()
""",
        "rust",
    )
    assert result.returncode == 0 and result.stdout == "owned sort arguments\n", result.stderr
    return  # noqa: PLR1711


def test_sort_keys_nested_orderable_results(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
def rank(value: int) -> list[tuple[str, int]]:
    return [("x", value % 3)]
def check() -> None:
    values: list[int] = [-9223372036854775808, 0, 3, 1, 4, 2, 9223372036854775807]
    ordered: list[int] = sorted(values, key=rank)
    assert ordered == [0, 3, -9223372036854775808, 1, 4, 9223372036854775807, 2]
    nested: list[list[int]] = [[], [1, 2], [1], [-1]]
    expected: list[list[int]] = [[1, 2], [1], [-1], []]
    assert sorted(nested, reverse=True) == expected
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


def test_sort_key_project_imports_and_standalone_execution(tmp_path: Path) -> None:
    root = sources(
        tmp_path,
        {
            "model.py": """from dataclasses import dataclass
@dataclass
class Row:
    category: str
    number: int
""",
            "order.py": """from model import Row as Record
def rank(row: Record) -> str:
    return row.category
""",
            "main.py": """import order as ordering
from model import Row as Item
def main() -> None:
    rows: list[Item] = [Item("a", 3), Item("b", 1), Item("a", 2)]
    for row in sorted(rows, key=ordering.rank, reverse=True):
        print(row.number)
    return
if __name__ == "__main__":
    main()
""",
        },
    )
    binary = build(root, tmp_path / "rust")
    expected = subprocess.run([sys.executable, str(root / "main.py")], capture_output=True, text=True, check=True)
    actual = subprocess.run(
        [str(binary)],
        env=dict(os.environ, PATH="/nonexistent", PYTHONHOME="/nonexistent", PYTHONPATH="/nonexistent"),
        capture_output=True,
        text=True,
        check=True,
    )
    assert actual.stdout == expected.stdout == "1\n3\n2\n"
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "expression,message",
    [
        ("sorted()", "one positional list"),
        ("sorted([1], rank)", "one positional list"),
        ("sorted([1], other=True)", "unique key and reverse"),
        ("sorted([1], **options)", "unique key and reverse"),
        ("sorted([1], key=lambda item: item)", "named annotated function"),
        ('sorted([1], key="rank")', "named annotated function"),
        ("sorted([1], key=missing)", "named annotated function"),
        ("sorted([1], key=two)", "one argument"),
        ("sorted([1], key=decimal)", "ordered non-float"),
        ("sorted([1], key=unique)", "ordered non-float"),
        ("sorted([1], key=wide)", "ordered non-float"),
        ("sorted(numbers, key=text)", "expected Type"),
        ("sorted([1], reverse=1)", "expected Type"),
        ('sorted("text", key=rank)', "expected Type|typed list"),
        ("sorted([1], reverse=True, reverse=False)", "unique key and reverse"),
    ],
)
def test_sort_key_diagnostics(expression: str, message: str) -> None:
    source = """
def rank(value: int) -> int:
    return value
def text(value: str) -> str:
    return value
def two(left: int, right: int) -> int:
    return left
def decimal(value: int) -> float:
    return float(value)
def unique(value: int) -> set[int]:
    return {value}
def wide(value: int) -> tuple[int, int, int, int, int, int, int, int, int, int, int, int, int]:
    return (value, value, value, value, value, value, value, value, value, value, value, value, value)
def check() -> None:
    numbers: list[int] = [1]
    options: dict[str, bool] = {"reverse": True}
    EXPRESSION
    return
if __name__ == "__main__":
    check()
""".replace("EXPRESSION", expression)
    with pytest.raises(ServiceError, match=message):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711
