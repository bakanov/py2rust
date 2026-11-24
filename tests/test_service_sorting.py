"""Recursive sequence sorting follows Python's lexicographic value order."""

import json
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_nested_sequence_sorting_order_copies_and_evaluation(tmp_path: Path, engine: str) -> None:
    rng = random.Random(48049)
    pairs = [[], [[]], [[0]], [[0], []], [[-1, 2]], [[-1, 2, 0]]]
    pairs.extend([[rng.choices(range(-5, 6), k=rng.randrange(5)) for _ in range(rng.randrange(5))] for _ in range(400)])
    source = """
from py2rust.stdlib import json_dumps
def observed() -> list[list[str]]:
    print("once")
    return [["é"], [], ["a", "z"], ["a"], ["😀"], ["a"]]
def check() -> None:
    names: list[list[str]] = sorted(observed())
    expected_names: list[list[str]] = [[], ["a"], ["a"], ["a", "z"], ["é"], ["😀"]]
    assert names == expected_names
    source: list[list[list[int]]] = VALUES
    copied: list[list[list[int]]] = sorted(source)
    original: list[list[list[int]]] = VALUES
    assert source == original
    source.sort()
    assert source == copied
    print(json_dumps(copied))
    input: list[list[int]] = [[2], [1]]
    output: list[list[int]] = sorted(input)
    output[0] = [1, 3]
    assert input == [[2], [1]] and output == [[1, 3], [2]]
    mixed: list[tuple[list[int], str]] = [([1], "b"), ([], "z"), ([1], "a")]
    mixed.sort()
    expected_mixed: list[tuple[list[int], str]] = [([], "z"), ([1], "a"), ([1], "b")]
    assert mixed == expected_mixed
    return
if __name__ == "__main__":
    check()
""".replace("VALUES", repr(pairs))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    output = result.stdout.splitlines()
    assert output[0] == "once" and json.loads(output[1]) == sorted(pairs)
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "annotation,value",
    [
        ("list[list[float]]", "[[1.0]]"),
        ("list[set[int]]", "[{1}]"),
        ("list[list[Json]]", "[[None]]"),
        ("list[dict[str,int]]", '[{"x":1}]'),
    ],
)
def test_nested_sorting_rejects_values_without_total_order(annotation: str, value: str) -> None:
    for operation in ["sorted(values)", "values.sort()"]:
        with pytest.raises(ServiceError, match="ordered non-float"):
            ServiceCompiler().compile(
                "from py2rust.stdlib import Json\ndef check() -> None:\n    values: "
                + annotation
                + " = "
                + value
                + "\n    "
                + operation
                + "\n    return\nif __name__ == '__main__':\n    check()\n"
            )
    return  # noqa: PLR1711
