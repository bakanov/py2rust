"""Typed set algebra preserves membership, operand values and evaluation order."""

import itertools
import json
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_set_algebra_membership_oracle_and_laws(tmp_path: Path, engine: str) -> None:
    universe = [-2, -1, 0, 1, 2]
    groups = [list(items) for size in range(6) for items in itertools.combinations(universe, size)]
    pairs = list(itertools.product(groups, groups))
    rng = random.Random(540054)
    pairs += [
        (rng.sample(range(-200, 201), rng.randrange(50)), rng.sample(range(-200, 201), rng.randrange(50)))
        for _ in range(300)
    ]
    expected = []
    for left, right in pairs:
        candidates = sorted(set(left + right))
        expected.append(
            [
                [item for item in candidates if item in left and item in right],
                [item for item in candidates if item in left or item in right],
                [item for item in candidates if item in left and item not in right],
                [item for item in candidates if (item in left) != (item in right)],
            ]
        )
    (tmp_path / "pairs.json").write_text(json.dumps(pairs))
    source = """
from py2rust.stdlib import Json, json_array, json_int, json_loads, read_text, json_dumps
def check() -> None:
    pairs: list[Json] = json_array(json_loads(read_text("pairs.json")))
    results: list[list[list[int]]] = []
    for pair in pairs:
        left_values: list[int] = []
        right_values: list[int] = []
        for value in json_array(pair[0]):
            left_values.append(json_int(value))
        for value in json_array(pair[1]):
            right_values.append(json_int(value))
        left: set[int] = set(left_values)
        right: set[int] = set(right_values)
        both: set[int] = left & right
        either: set[int] = left | right
        only: set[int] = left - right
        different: set[int] = left ^ right
        assert both == left.intersection(right)
        assert either == left.union(right)
        assert only == left.difference(right)
        assert different == left.symmetric_difference(right)
        assert left == set(left_values) and right == set(right_values)
        assert both | different == either
        assert (left - right) | both == left
        assert len(left ^ left) == 0
        results.append([sorted(list(both)), sorted(list(either)), sorted(list(only)), sorted(list(different))])
        either.add(999)
        assert 999 not in left and 999 not in right
    print(json_dumps(results))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    return  # noqa: PLR1711


def test_set_algebra_types_nested_calls_and_evaluation(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from enum import Enum
from py2rust.stdlib import pretty
class Kind(Enum):
    LOW = 1
    HIGH = 2
def observed(label: str, value: int) -> set[int]:
    print(label)
    return {value}
def failing() -> set[int]:
    print("fail")
    assert False, "operand failure"
    return {0}
def check() -> None:
    value: set[int] = observed("left", 1) | observed("right", 2)
    assert value == {1, 2}
    value = observed("receiver", 3).union(observed("argument", 4))
    assert value == {3, 4}
    value = (observed("nested-a", 1) | observed("nested-b", 2)) & observed("nested-c", 2)
    assert value == {2}
    try:
        value = failing() ^ observed("forbidden", 0)
    except Exception:
        assert value == {2}
    words: set[str] = {"é", "世界", "😀", ""}
    common: set[str] = words & {"😀", ""}
    print(pretty(sorted(list(common))))
    flags: set[bool] = {True, False} - {False}
    assert flags == {True}
    pairs: set[tuple[int, str]] = {(1, "a"), (2, "b")}
    others: set[tuple[int, str]] = {(2, "b"), (3, "c")}
    assert pairs ^ others == {(1, "a"), (3, "c")}
    varied: set[tuple[int, ...]] = {(), (1,), (1, 2)}
    more: set[tuple[int, ...]] = {(1,), (2,)}
    assert len(varied.intersection(more)) == 1
    kinds: set[Kind] = {Kind.LOW}
    assert len(kinds.union({Kind.HIGH})) == 2
    empty: set[int] = set()
    assert empty | {1} == {1} and {1} - empty == {1}
    assert value.union(set()) == value
    return
if __name__ == "__main__":
    check()
""",
    )
    assert "forbidden" not in output
    assert output.splitlines()[:8] == [
        "left",
        "right",
        "receiver",
        "argument",
        "nested-a",
        "nested-b",
        "nested-c",
        "fail",
    ]
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "expression",
    [
        "left | [1]",
        "left & {True}",
        'left - {"1"}',
        "left ^ {1.0}",
        "left + {1}",
        "left.union([1])",
        "left.union({True})",
        "left.intersection()",
        "left.union({1}, {2})",
        "left.symmetric_difference(other={1})",
        "left.difference(1)",
    ],
)
def test_set_algebra_rejects_mixed_types_and_unsupported_calls(expression: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "def check() -> None:\n    left: set[int] = {1}\n    "
            + expression
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
