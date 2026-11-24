"""Dictionary-key sorting, stable callback ties, tuple keys and evaluation order."""

import json
from pathlib import Path

import pytest

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_sorted_dictionary_keys(tmp_path: Path, engine: str) -> None:
    result = run(
        tmp_path,
        """
from py2rust.stdlib import json_dumps
def length(value: str) -> int:
    return len(value)
def check() -> None:
    names: dict[str,int] = {"é": 2, "z": 1, "aa": 9, "😀": 3, "bb": 0}
    print(json_dumps(sorted(names)))
    print(json_dumps(sorted(names, reverse=True)))
    print(json_dumps(sorted(names, key=length)))
    print(json_dumps(sorted(names, key=length, reverse=True)))
    print(json_dumps(list(names)))
    numeric: dict[int,str] = {2:"b", -1:"a", 0:"c"}
    print(json_dumps(sorted(numeric)))
    pairs: dict[tuple[str,int],str] = {("b",0):"x", ("a",2):"y", ("a",-1):"z"}
    print(json_dumps(sorted(pairs)))
    empty: dict[str,int] = {}
    print(json_dumps(sorted(empty, key=length)))
    return
if __name__ == "__main__":
    check()
""",
        engine,
    )
    assert result.returncode == 0 and not result.stderr, result.stderr
    names = {"é": 2, "z": 1, "aa": 9, "😀": 3, "bb": 0}
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        sorted(names),
        sorted(names, reverse=True),
        sorted(names, key=len),
        sorted(names, key=len, reverse=True),
        list(names),
        [-1, 0, 2],
        [["a", -1], ["a", 2], ["b", 0]],
        [],
    ]
    return  # noqa: PLR1711


def test_sorted_dictionary_single_evaluation_and_callback_order(tmp_path: Path) -> None:
    output = parity(
        tmp_path,
        """
from py2rust.stdlib import json_dumps
def observed() -> dict[str,int]:
    print("dictionary")
    return {"bb":1,"a":2,"cc":3}
def direction() -> bool:
    print("reverse")
    return True
def key(value: str) -> int:
    print(value)
    return len(value)
def check() -> None:
    print(json_dumps(sorted(observed(), key=key, reverse=direction())))
    return
if __name__ == "__main__":
    check()
""",
    )
    assert output.splitlines() == ["dictionary", "reverse", "bb", "a", "cc", '["bb","cc","a"]']
    return  # noqa: PLR1711
