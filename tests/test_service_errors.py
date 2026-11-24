"""Recoverable Result failures and nonlocal returns across protected blocks."""

from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity


def test_recoverable_errors_nested_returns_and_else(tmp_path):
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_int, read_text

def early(value: int) -> int:
    try:
        try:
            assert value > 0, "positive required"
            return value + 10
        except Exception as problem:
            assert str(problem) == "positive required"
            return -1
    except Exception:
        return -2
    return 99

def run() -> None:
    total: int = 0
    for step in range(3):
        try:
            parsed: Json = json_loads("bad")
            total = 100
        except Exception:
            total = total + 1
        else:
            total = 200
    try:
        number: Json = json_loads("7")
        total = total + json_int(number)
    except Exception:
        total = 300
    else:
        total = total + 10
    assert total == 20
    assert early(3) == 13
    assert early(0) == -1
    try:
        for index in range(5):
            if index == 2:
                break
            total = total + 1
        assert False, "expected failure"
    except Exception as failure:
        assert str(failure) == "expected failure"
        total = total + 1
    assert total == 23
    try:
        try:
            assert True, "ignored"
        except Exception:
            total = 400
        else:
            assert False, "else escapes its own handler"
    except Exception:
        total = total + 1
    assert total == 24
    print("recoverable errors and returns agree")
if __name__ == "__main__":
    run()
""",
    )


@pytest.mark.parametrize(
    "statement",
    [
        "try:\n    pass\nexcept ValueError:\n    pass",
        "try:\n    pass\nexcept Exception:\n    pass\nexcept Exception:\n    pass",
        "while True:\n    try:\n        break\n    except Exception:\n        pass",
    ],
)
def test_unsupported_exception_forms_have_diagnostics(statement):
    source = "def run() -> None:\n" + "\n".join("    " + line for line in statement.splitlines())
    source += "\nif __name__ == '__main__':\n    run()\n"
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(source)


def test_total_return_paths_and_exception_binding(tmp_path):
    parity(
        tmp_path,
        """
from py2rust.stdlib import Json, json_loads, json_int

def choose(text: str) -> int:
    try:
        value: Json = json_loads(text)
        if json_int(value) > 0:
            return 1
        else:
            return 2
    except Exception:
        return 3

def run() -> None:
    assert choose("5") == 1
    assert choose("-5") == 2
    assert choose("broken") == 3
    print("every path returns")
    return
if __name__ == "__main__":
    run()
""",
    )


def test_bare_raise_nested_handlers_and_resource_cleanup(tmp_path: Path) -> None:
    parity(
        tmp_path,
        """
from py2rust.stdlib import FileHandle, file_open, file_read, file_size, write_text

def propagate() -> int:
    try:
        assert False, "original 世界"
    except Exception as outer:
        try:
            raise
        except Exception as inner:
            assert str(inner) == str(outer)
        try:
            assert False, "different inner error"
        except Exception as other:
            assert str(other) == "different inner error"
            try:
                raise
            except Exception as deepest:
                assert str(deepest) == str(other)
        try:
            pass
        except Exception:
            return -1
        else:
            raise
    return -2

def run() -> None:
    write_text("resource", "readable")
    handle: FileHandle = file_open("resource", "rb")
    caught: int = 0
    try:
        with handle as scoped:
            try:
                assert file_read(scoped, 1) == b"r"
                assert False, "close before propagate"
            except Exception:
                raise
    except Exception as failure:
        assert str(failure) == "close before propagate"
        caught = caught + 1
    try:
        file_size(handle)
    except Exception:
        caught = caught + 1
    try:
        propagate()
    except Exception as propagated:
        assert str(propagated) == "original 世界"
        caught = caught + 1
    for attempt in range(2):
        try:
            try:
                assert False, "loop error"
            except Exception:
                if attempt == 0:
                    raise
                assert False, "replacement failure"
        except Exception as loop_error:
            assert str(loop_error) == ("loop error" if attempt == 0 else "replacement failure")
            caught = caught + 1
    assert caught == 5
    print("bare raise, nested restoration and resource cleanup passed")
    return

if __name__ == "__main__":
    run()
""",
    )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize(
    "statement",
    [
        "raise",
        "raise Exception('message')",
        "try:\n    pass\nexcept Exception:\n    pass\nraise",
        "try:\n    raise\nexcept Exception:\n    pass",
        "try:\n    pass\nexcept Exception:\n    raise Exception('other')",
    ],
)
def test_raise_outside_handler_and_explicit_raises_have_diagnostics(statement: str) -> None:
    source = "def run() -> None:\n" + "\n".join("    " + line for line in statement.splitlines())
    source += "\nif __name__ == '__main__':\n    run()\n"
    with pytest.raises(ServiceError, match="bare re-raising"):
        ServiceCompiler().compile(source)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_empty_collections_hex_and_json_comparison(tmp_path):
    parity(
        tmp_path,
        r"""
from py2rust.stdlib import Json, json_equal, json_keys, json_loads, json_dumps

def run() -> None:
    labels: set[str] = set()
    labels.add("世界")
    numbers: list[int] = list()
    numbers.append(2)
    numbers.extend(numbers)
    copied: list[int] = numbers.copy()
    copied.append(3)
    assert numbers == [2, 2] and copied == [2, 2, 3]
    assert min(3, -1) == -1 and max(3, -1) == 3
    assert min("a", "b") == "a" and max(1.0, 2.0) == 2.0
    mapping: dict[str, int] = dict()
    mapping["two"] = 2
    assert "世界" in labels and numbers[0] == mapping["two"]
    blob: bytes = bytes.fromhex(" 00 ff FE\t\n0a\v0b\f0c ")
    assert blob.hex() == "00fffe0a0b0c"
    assert bytes.fromhex("").hex() == ""
    rejected: int = 0
    for text in ["a", "0 a", "gg", "０１", "00\u00a0ff"]:
        try:
            bad: bytes = bytes.fromhex(text)
        except Exception:
            rejected = rejected + 1
    assert rejected == 5
    value: Json = {"present": None}
    assert json_keys({"z": None, "a": True}) == ["a", "z"]
    assert json_equal(json_loads(json_dumps({"a": [1, "two"], "flag": True})), {"a": [1, "two"], "flag": True})
    assert "present" in value and "absent" not in value
    array: Json = ["a", 1, "b"]
    assert "a" in array and "1" not in array
    word: Json = "世界"
    assert "世" in word
    scalar: Json = 5
    try:
        invalid: bool = "x" in scalar
    except Exception:
        rejected = rejected + 1
    assert rejected == 6
    assert json_equal({"a": [1, 2.0]}, {"a": [1.0, 2]})
    assert not json_equal({"a": [True]}, {"a": [1]})
    assert not json_equal(9007199254740993, 9007199254740992.0)
    assert not json_equal(9223372036854775807, 9223372036854775808.0)
    assert json_equal(-9223372036854775808, -9223372036854775808.0)
    assert json_equal(json_loads("1e0"), 1)
    assert json_equal([None, "世界"], [None, "世界"])
    print("collections, codecs and strict JSON agree")
    return
if __name__ == "__main__":
    run()
""",
    )


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_system_exit_bypasses_exception_handler(tmp_path, engine):
    from .test_services import run

    result = run(
        tmp_path,
        """
import sys

def run() -> None:
    try:
        print("written before exit")
        sys.exit(7)
    except Exception:
        print("must not catch SystemExit")
    return
if __name__ == "__main__":
    run()
""",
        engine,
    )
    assert result.returncode == 7
    assert result.stdout == "written before exit\n"
