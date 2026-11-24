"""Nested list writes preserve value/index evaluation order, recoverable bounds and owned storage."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_nested_assignment_bounds_depth_and_values(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from dataclasses import dataclass
from py2rust.stdlib import Json, json_string, FileHandle, file_open, file_write, file_seek, file_read
@dataclass
class Item:
    name: str
def check() -> None:
    grid: list[list[int]] = [[1, 2], [3], []]
    grid[-3][-1] = 20
    grid[-2][0] = 30
    expected: list[list[int]] = [[1, 20], [30], []]
    assert grid == expected
    caught: int = 0
    for row in [-9223372036854775808, -4, 3, 9223372036854775807]:
        try:
            grid[row][0] = 99
        except Exception:
            caught = caught + 1
    for column in [-9223372036854775808, -3, 2, 9223372036854775807]:
        try:
            grid[0][column] = 99
        except Exception:
            caught = caught + 1
    try:
        grid[2][0] = 99
    except Exception:
        caught = caught + 1
    assert caught == 9 and grid == expected
    cube: list[list[list[str]]] = [[['a', 'b']], [['c']]]
    cube[-1][0][-1] = '世界'
    assert cube[1][0][0] == '世界'
    cube[0][0] = ['replacement']
    assert cube[0][0] == ['replacement']
    records: list[list[Item]] = [[Item('old')]]
    records[0][0] = Item('new')
    assert records[0][0].name == 'new'
    objects: list[list[Json]] = [[None]]
    objects[0][0] = {'name': 'value'}
    assert json_string(objects[0][0]['name']) == 'value'
    with file_open('nested.bin', 'w+b') as handle:
        handles: list[list[FileHandle]] = [[handle]]
        handles[0][0] = handle
        file_write(handles[0][0], b'x')
        file_seek(handle, 0, 0)
        assert file_read(handle, 1) == b'x'
    print(caught)
    return
if __name__ == '__main__':
    check()
""",
    )
    assert output == "9\n"
    return  # noqa: PLR1711


def test_nested_assignment_evaluation_and_failure_order(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def emit(label: str, value: int) -> int:
    print(label)
    return value
def failure() -> int:
    print('failed value')
    assert False, 'injected value failure'
    return 0
def check() -> None:
    grid: list[list[int]] = [[1], [0], [0]]
    grid[emit('outer', 0)][emit('inner', 0)] = emit('value', 7)
    assert grid[0][0] == 7
    try:
        grid[emit('bad outer', 99)][emit('must not run', 0)] = emit('before outer error', 8)
    except Exception:
        print('outer caught')
    try:
        grid[emit('good outer', 0)][emit('bad inner', 99)] = emit('before inner error', 8)
    except Exception:
        print('inner caught')
    try:
        grid[emit('must not run', 0)][0] = failure()
    except Exception:
        print('value caught')
    grid[grid.pop()[0]][0] = emit('outer mutates before lookup', 9)
    assert grid == [[9], [0]]
    grid[0][0] = grid.pop()[0]
    assert grid == [[0]]
    indices: list[int] = [0, 0]
    grid[indices.pop()][indices.pop()] = 11
    assert len(indices) == 0 and grid == [[11]]
    grid[0][grid[0][0] - 11] = 12
    assert grid == [[12]]
    print('finished')
    return
if __name__ == '__main__':
    check()
""",
    )
    assert output == (
        "value\nouter\ninner\nbefore outer error\nbad outer\nouter caught\n"
        "before inner error\ngood outer\nbad inner\ninner caught\nfailed value\nvalue caught\n"
        "outer mutates before lookup\nfinished\n"
    )
    return  # noqa: PLR1711


def test_nested_assignment_large_grid(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
def check() -> None:
    grid: list[list[int]] = []
    for row in range(1024):
        values: list[int] = []
        for column in range(1024):
            values.append(0)
        grid.append(values.copy())
    total: int = 0
    for row in range(1024):
        for column in range(1024):
            grid[row][column] = row + column
            total = total + grid[row][column]
    assert grid[-1][-1] == 2046
    print(total)
    return
if __name__ == '__main__':
    check()
""",
    )
    assert output == str(1024 * 1024 * 1023) + "\n"
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        'grid[0]["0"] = 1',
        "grid[True][0] = 1",
        'grid[0][0] = "bad"',
        "grid[0][:] = [1]",
        "grid[:][0] = [1]",
        "grid[0][len(grid.pop()) - 1] = 1",
        "grid[0][len(grid[0].append(2))] = 1",
        'mapping["x"][0] = 1',
        'words[0][0] = "x"',
        "fixed[0][0] = 1",
    ],
)
def test_nested_assignment_rejects_unsupported_paths(statement: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile("""
def check() -> None:
    grid: list[list[int]] = [[0]]
    mapping: dict[str, list[int]] = {"x": [0]}
    words: list[str] = ["a"]
    fixed: tuple[list[int], int] = ([0], 1)
    STATEMENT
    return
if __name__ == '__main__':
    check()
""".replace("STATEMENT", statement))
    return  # noqa: PLR1711


@pytest.mark.parametrize(
    "statement",
    [
        "grid[0][heapq.heappop(grid)[0]] = 7",
        "grid[0][heapq.heapreplace(grid, [0])[0]] = 7",
        "grid[0].append(heapq.heappop(grid)[0])",
        "grid[0].extend(heapq.heapreplace(grid, [0]))",
    ],
)
def test_nested_assignment_rejects_heap_detachment(statement: str) -> None:
    with pytest.raises(ServiceError, match="cannot mutate its parent collection"):
        ServiceCompiler().compile(
            "import heapq\ndef check() -> None:\n    grid: list[list[int]] = [[0], [1]]\n    "
            + statement
            + "\n    return\nif __name__ == '__main__':\n    check()\n"
        )
    return  # noqa: PLR1711
