"""Chained comparisons evaluate shared operands once and short-circuit failures."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_chained_comparisons_evaluate_in_order_once(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import FileHandle, file_open, file_write, file_read, file_seek

def observed(label: str, value: int) -> int:
    print(label)
    return value

def forbidden() -> int:
    assert False, "short-circuited operand ran"
    return 0

def next_byte(handle: FileHandle) -> int:
    data: bytes = file_read(handle, 1)
    return data[0]

def check() -> None:
    assert observed("a", 0) < observed("b", 1) <= observed("c", 1) != observed("d", 2)
    assert not (observed("e", 3) < observed("f", 2) < forbidden())
    assert not (0 <= observed("g", 1) > observed("h", 2) != forbidden())
    assert -9223372036854775808 < 0 < 9223372036854775807
    assert 3.0 >= 3.0 > -1.0 != 0.0
    assert False < True == True
    assert "a" < "α" < "世" <= "世"
    assert b"a" < b"aa" < b"b"
    assert [1, 2] <= [1, 2] < [2, 0]
    assert (1, "a") < (1, "b") < (2, "a")
    assert {1} < {1, 2} <= {1, 2, 3}
    assert (0 < observed("nested", 1) < 2) == True == (3 > 2 > 1)
    with file_open("counter.bin", "w+b") as handle:
        file_write(handle, b"1234")
        file_seek(handle, 0, 0)
        assert 48 < next_byte(handle) < next_byte(handle) < next_byte(handle) < 53
        assert file_read(handle, 1) == b"4"
    caught: bool = False
    try:
        value: bool = 0 < observed("before-error", 1) < forbidden()
    except Exception:
        caught = True
    assert caught
    assert not (1 > 2 > (9223372036854775807 + 1))
    print("finished")
    return

if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["a", "b", "c", "d", "e", "f", "g", "h", "nested", "before-error", "finished"]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_mixed_membership_and_none_chains(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads

def named() -> str:
    print("name")
    return "alpha"

def mapping() -> dict[str, int]:
    print("mapping")
    return {"alpha": 1}

def optional() -> Json:
    print("optional")
    return None

def text() -> Json:
    print("text")
    return "present"

def check() -> None:
    expected: dict[str, int] = {"alpha": 1}
    assert "alpha" == named() in mapping() == expected
    assert "beta" not in expected == mapping()
    assert "alpha" in ["alpha", "beta"] == ["alpha", "beta"]
    assert "a" in "alpha" < "beta"
    assert 2 > 1 in {1, 2} < {1, 2, 3}
    assert None is optional() is None
    assert None is not text() is not None
    # The last identity operator deliberately uses a literal None as required.
    assert not (None is text() is None)
    value: Json = json_loads('{"x": 1}')
    assert "x" in value == json_loads('{"x": 1}')
    print("finished")
    return

if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["name", "mapping", "mapping", "optional", "text", "text", "finished"]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    "expression",
    ["1 < 2.0 < 3.0", '"a" < "b" in [1, 2]', "None is optional() is optional()"],
)
def test_invalid_chains_are_diagnosed(expression: str) -> None:
    source = (
        "from py2rust.stdlib import Json\n"
        "def optional() -> Json:\n    return None\n"
        "def check() -> None:\n    print(" + expression + ")\n    return\n"
        'if __name__ == "__main__":\n    check()\n'
    )
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_set_comparisons_use_inclusion_not_lexicographic_order(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    sets: list[set[int]] = [set(), {1}, {2}, {3}, {1, 2}, {1, 3}, {2, 3}, {1, 2, 3}]
    for left in sets:
        for middle in sets:
            for right in sets:
                print(left < middle <= right, left >= middle > right, left != middle == right)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    values = [set(), {1}, {2}, {3}, {1, 2}, {1, 3}, {2, 3}, {1, 2, 3}]
    expected = [
        f"{left < middle <= right} {left >= middle > right} {left != middle == right}".lower()
        for left in values
        for middle in values
        for right in values
    ]
    assert result.stdout.lower().splitlines() == expected
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_nested_sequences_keep_set_partial_order(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
def check() -> None:
    sets: list[set[int]] = [set(), {1}, {2}, {1, 2}]
    for first in sets:
        for second in sets:
            for third in sets:
                print([first] < [second] <= [third], (first, 1) >= (second, 2) > (third, 0))
                print([[first], [second]] < [[second], [third]], [first, second] >= [second])
    assert not ([{1}] < [{2}])
    assert not (({1}, 0) > ({2}, -1))
    assert [{1}] < [{1}, {2}]
    assert ({1}, 3) > ({1}, 2)
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0, result.stderr
    values = [set(), {1}, {2}, {1, 2}]
    expected = []
    for first in values:
        for second in values:
            for third in values:
                expected.append(f"{[first] < [second] <= [third]} {(first, 1) >= (second, 2) > (third, 0)}".lower())
                expected.append(f"{[[first], [second]] < [[second], [third]]} {[first, second] >= [second]}".lower())
    assert result.stdout.lower().splitlines() == expected
    return  # noqa: PLR1711 - explicit return required by repository guidelines
