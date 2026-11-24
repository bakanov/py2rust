"""Immutable variadic tuples and composite dictionary keys compile without serialization tricks."""

import subprocess
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, program


def test_tuple_keys_collections_and_dynamic_sequences(tmp_path: Path) -> None:
    result = parity(
        tmp_path,
        """
from enum import Enum
from py2rust.stdlib import pretty
class Kind(Enum):
    A = 1
    B = 2
def source() -> list[str]:
    print("source")
    return ["ab", "c", "世界"]
def key() -> tuple[str, ...]:
    return tuple(source())
def check() -> None:
    original: list[str] = source()
    values: tuple[str, ...] = tuple(original)
    original.append("later")
    assert len(values) == 3 and values[-1] == "世界"
    assert values == ("ab", "c", "世界") and ("ab", "c", "世界") == values
    assert values[1:-1] == ("c",)
    assert "世界" in values and "later" not in values
    empty: tuple[str, ...] = ()
    other_empty: tuple[str, ...] = tuple()
    assert empty == other_empty and len(empty) == 0
    seen: list[str] = []
    for item in key():
        seen.append(item)
    assert seen == list(values)
    mapping: dict[tuple[str, ...], list[int]] = {}
    mapping[values] = [1]
    mapping[values].append(2)
    mapping[("a", "bc", "世界")] = [3]
    mapping[("ab", "c")] = [4]
    mapping[empty] = [5]
    assert mapping.get(key(), []) == [1, 2]
    assert ("a", "bc", "世界") in mapping
    assert ("ab", "c", "世界", "") not in mapping
    assert mapping[("ab", "c")] == [4]
    keys: list[tuple[str, ...]] = sorted(list(mapping))
    print(pretty(keys))
    assert keys[0] == empty
    del mapping[("ab", "c")]
    assert len(mapping) == 3
    fixed: dict[tuple[str, int, Kind], int] = {("x", 2, Kind.A): 7}
    assert fixed[("x", 2, Kind.A)] == 7
    nested: set[tuple[tuple[str, ...], bool]] = {(values, True), (empty, False)}
    assert (values, True) in nested
    fixed_words: tuple[str, str] = ("one", "two")
    words: tuple[str, ...] = tuple(fixed_words)
    assert fixed_words[0] == "one" and words == fixed_words
    assert list(fixed_words) == ["one", "two"] and fixed_words[1] == "two"
    scalars: tuple[int, ...] = tuple((1, 2, 3))
    assert scalars[-1] == 3
    table: dict[tuple[tuple[int, ...], str], str] = {(scalars, "a"): "found"}
    assert table[(scalars, "a")] == "found"
    caught: bool = False
    try:
        invalid: str = empty[0]
    except Exception:
        caught = True
    assert caught
    return
if __name__ == "__main__":
    check()
""",
    )
    assert result.count("source\n") == 3
    return  # noqa: PLR1711


def test_variadic_tuple_order_with_nested_sets(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
def check() -> None:
    a: tuple[set[int], ...] = ({1},)
    b: tuple[set[int], ...] = ({2},)
    c: tuple[set[int], ...] = ({1, 2},)
    d: tuple[set[int], ...] = ({1}, {2})
    assert not (a < b) and not (a >= b)
    assert a < c and c > b and a <= c
    assert a < d and d > a
    assert a == ({1},)
    print("partial order passed")
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        "items: dict[tuple[list[int]], str] = {}",
        "items: dict[tuple[float, ...], str] = {}",
        "items: set[tuple[dict[str, int], ...]] = set()",
        "items: dict[tuple[" + ",".join(["int"] * 13) + "], int] = {}",
        'items: tuple[int, ...] = (1, "x")',
        "items: tuple[int, ...] = (1,)\n    items[0] = 2",
        "items: tuple[int, ...] = (1,)\n    items.append(2)",
    ],
)
def test_invalid_tuple_types_and_mutation_rejected(statement: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "def check() -> None:\n    " + statement + "\n    return\n" 'if __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711


def test_record_collection_reads_borrow_large_fields(tmp_path: Path) -> None:
    source = """
from dataclasses import dataclass
from py2rust.stdlib import read_text
@dataclass
class Table:
    rows: list[str]
def rows() -> list[str]:
    block: str = read_text("block.txt")
    result: list[str] = []
    for number in range(40000):
        result.append(block)
    return result
def check() -> None:
    table: Table = Table(rows())
    assert len(table.rows) == 40000
    total: int = 0
    for number in range(len(table.rows)):
        total = total + len(table.rows[number])
    assert total == 40960000
    selected: str = table.rows[-1]
    assert len(selected) == 1024
    print("borrowed record fields passed")
    return
if __name__ == "__main__":
    check()
"""
    (tmp_path / "block.txt").write_text("x" * 1024)
    command = program(tmp_path, source, "rust", "record_fields")
    result = subprocess.run(
        ["/usr/bin/prlimit", "--as=134217728", "--", *command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "borrowed record fields passed\n", result.stderr
    return  # noqa: PLR1711


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_fixed_tuple_collection_paths_keep_evaluation_and_owned_results(tmp_path: Path, engine: str) -> None:
    source = """
from dataclasses import dataclass
@dataclass
class Container:
    content: tuple[list[str], bytes]
def position() -> int:
    print("position")
    return 0
def temporary() -> tuple[list[str], bytes]:
    print("temporary")
    return (["new"], b"abc")
def check() -> None:
    data: tuple[list[str], bytes] = (["first", "世界"], b"ABC")
    assert len(data[0]) == 2 and data[0][-1] == "世界"
    assert "first" in data[0] and 66 in data[1]
    assert data[0][0].startswith("fir") and data[1][-1] == 67
    assert data[1][1:] == b"BC"
    rows: list[tuple[list[str], bytes]] = [data]
    assert len(rows[position()][0]) == 2
    assert rows[position()][1][1] == 66
    mapping: dict[str, tuple[list[str], bytes]] = {"row": data}
    assert len(mapping["row"][1]) == 3
    item: Container = Container(data)
    assert item.content[0][0] == "first"
    assert len(item.content[1]) == 3
    nested: tuple[tuple[list[str], bytes], int] = (data, 7)
    assert len(nested[0][0]) == 2
    assert len(temporary()[0]) == 1
    assert temporary()[1][-1] == 99
    copied: list[str] = list(data[0])
    copied.append("extra")
    assert len(data[0]) == 2 and len(copied) == 3
    try:
        print(rows[position()][0][3])
    except Exception:
        print("bounds caught")
    return
if __name__ == "__main__":
    check()
"""
    command = program(tmp_path, source, engine, "tuple_paths")
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 0 and not result.stderr, result
    assert result.stdout.splitlines() == ["position", "position", "temporary", "temporary", "position", "bounds caught"]
    return  # noqa: PLR1711 - explicit repository returns
