"""Heap operations retain Python order, in-place changes and argument evaluation."""

import heapq
import json
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_heaps_against_heapq_and_sorted_oracle(tmp_path: Path, engine: str) -> None:
    rng = random.Random(53007)
    batches = [[], [1], [2, 1], [2, 1, 1], [-(2**63), 2**63 - 1, 0]]
    batches += [rng.choices(range(-50, 51), k=rng.randrange(120)) for _ in range(80)]
    batches += [rng.choices(range(-5000, 5001), k=3001)]
    expected = []
    for values in batches:
        heap = values.copy()
        heapq.heapify(heap)
        popped = [heapq.heappop(heap) for _ in range(len(heap))]
        assert popped == sorted(values)
        expected.append(popped)
    operations = [(rng.randrange(4), rng.randrange(-100, 101)) for _ in range(2000)]
    heap, history = [], []
    for operation, item in operations:
        if operation == 0:
            result = heapq.heappush(heap, item)
        elif operation == 1:
            result = heapq.heappop(heap) if heap else None
        elif operation == 2:
            result = heapq.heapreplace(heap, item) if heap else None
        else:
            result = heapq.heappushpop(heap, item)
        history.append({"value": result, "heap": heap.copy()})
    source = """
import heapq
from py2rust.stdlib import Json, json_dumps
def check() -> None:
    batches: list[list[int]] = BATCHES
    results: list[list[int]] = []
    for values in batches:
        heapq.heapify(values)
        popped: list[int] = []
        while len(values) > 0:
            popped.append(heapq.heappop(values))
        results.append(popped)
    print(json_dumps(results))
    heap: list[int] = []
    operations: list[tuple[int, int]] = OPERATIONS
    history: list[Json] = []
    for operation in operations:
        result: Json = None
        if operation[0] == 0:
            heapq.heappush(heap, operation[1])
        elif operation[0] == 1:
            try:
                result = heapq.heappop(heap)
            except Exception:
                assert len(heap) == 0
        elif operation[0] == 2:
            try:
                result = heapq.heapreplace(heap, operation[1])
            except Exception:
                assert len(heap) == 0
        else:
            result = heapq.heappushpop(heap, operation[1])
        history.append({"value": result, "heap": heap.copy()})
    print(json_dumps(history))
    return
if __name__ == "__main__":
    check()
""".replace("BATCHES", repr(batches)).replace("OPERATIONS", repr(operations))
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert json.loads(lines[0]) == expected
    assert json.loads(lines[1]) == history
    return  # noqa: PLR1711


def test_heap_tuples_sequences_empty_errors_and_evaluation(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
import heapq
from py2rust.stdlib import pretty
def fail() -> int:
    print("item evaluated")
    assert False, "item failure"
    return 0
def check() -> None:
    jobs: list[tuple[int, int, str]] = [(1, 9, "z"), (0, 5, "a"), (1, 8, "b"), (1, 8, "é")]
    heapq.heapify(jobs)
    heapq.heappush(jobs, (1, 8, "😀"))
    while len(jobs) > 0:
        print(pretty(heapq.heappop(jobs)))
    words: list[str] = ["世界", "é", "a", "😀", ""]
    heapq.heapify(words)
    print(pretty(words))
    flags: list[bool] = [True, False, True, False]
    heapq.heapify(flags)
    print(pretty(flags))
    nested: list[tuple[list[int], str]] = [([1, 0], "a"), ([1], "b"), ([], "c"), ([1], "a")]
    heapq.heapify(nested)
    while len(nested) > 0:
        print(pretty(heapq.heappop(nested)))
    varied: list[tuple[int, ...]] = [(1, 2), (), (1,), (0,)]
    heapq.heapify(varied)
    print(pretty(varied))
    heap: list[int] = [1, 2, 3]
    heapq.heappush(heap, heapq.heappop(heap))
    assert heap == [1, 3, 2]
    first: int = heapq.heapreplace(heap, heap.pop())
    assert first == 1 and heap == [2, 3]
    heapq.heappush(heap, heap.pop())
    assert heap == [2, 3]
    try:
        heapq.heappush(heap, fail())
    except Exception:
        assert heap == [2, 3]
    heap.clear()
    heapq.heapify(heap)
    item: int = heapq.heappushpop(heap, 7)
    assert item == 7 and len(heap) == 0
    for attempt in range(2):
        try:
            if attempt == 0:
                heapq.heappop(heap)
            else:
                heapq.heapreplace(heap, fail())
        except Exception as error:
            print(str(error))
        assert len(heap) == 0
    return
if __name__ == "__main__":
    check()
""",
    )
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "annotation,value",
    [
        ("list[float]", "[1.0]"),
        ("list[Json]", "[None]"),
        ("list[tuple[int,float]]", "[(1,2.0)]"),
        ("list[set[int]]", "[{1}]"),
        ("dict[str,int]", '{"a":1}'),
    ],
)
def test_heap_rejects_nonordered_types(annotation: str, value: str) -> None:
    with pytest.raises(ServiceError, match="ordered non-float"):
        ServiceCompiler().compile(
            "import heapq\nfrom py2rust.stdlib import Json\ndef check() -> None:\n    heap: "
            + annotation
            + " = "
            + value
            + '\n    heapq.heapify(heap)\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        "heapq.heapify([])",
        "heapq.heappush(heap)",
        "heapq.heappop(heap, 1)",
        "heapq.heapreplace(heap)",
        'heapq.heappush(heap, "bad")',
        "heapq.heappush(heap, True)",
        "heapq.heappushpop(heap, item=1)",
        "heapq.nsmallest(1, heap)",
        "heapq.heapify(heap.copy())",
    ],
)
def test_heap_rejects_unsupported_calls(statement: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(
            "import heapq\ndef check() -> None:\n    heap: list[int] = []\n    "
            + statement
            + '\n    return\nif __name__ == "__main__":\n    check()\n'
        )
    return  # noqa: PLR1711
