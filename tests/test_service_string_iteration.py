"""Iterate Unicode scalar strings with Python evaluation and loop-control behavior."""

import json
import random
from pathlib import Path

import pytest

from .test_services import run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_iteration_matches_unicode_characters(tmp_path: Path, engine: str) -> None:
    values = ["", "abc", "é😀e\u0301", "\0\r\n\t", "世界", "\u200d\ufe0f", "\U0010ffff", "\ud7ff\ue000"]
    rng = random.Random(72072)
    for _ in range(200):
        numbers = [rng.randrange(0x110000) for _ in range(rng.randrange(25))]
        values.append("".join(chr(value) for value in numbers if not 0xD800 <= value <= 0xDFFF))
    (tmp_path / "strings.json").write_text(json.dumps(values))
    source = """from py2rust.stdlib import Json, read_text, json_loads, json_array, json_string, json_dumps
def check() -> None:
    rows: list[Json] = []
    for value in json_array(json_loads(read_text("strings.json"))):
        characters: list[str] = []
        for character in json_string(value):
            assert len(character) == 1
            characters.append(character)
        rows.append(characters)
    print(json_dumps(rows))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [list(value) for value in values]
    return  # noqa: PLR1711 - explicit repository returns


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_iteration_evaluation_snapshot_control_and_errors(tmp_path: Path, engine: str) -> None:
    source = """def observed(value: str) -> str:
    print("evaluated")
    return value
def broken() -> str:
    assert False, "broken iterator"
    return ""
def first(value: str) -> str:
    for character in value:
        return character
    return "empty"
def check() -> None:
    text: str = "aé😀z"
    seen: str = ""
    for character in observed(text):
        text = "changed"
        if character == "é":
            continue
        if character == "z":
            break
        seen = seen + character
        character = "replacement"
    print(seen)
    print(text)
    for outer in "é😀":
        for inner in "x世":
            print(outer + inner)
    for character in observed(""):
        assert False
    print(first("😀x"))
    print(first(""))
    try:
        for character in broken():
            assert False
    except Exception:
        print("caught")
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "evaluated",
        "a😀",
        "changed",
        "éx",
        "é世",
        "😀x",
        "😀世",
        "evaluated",
        "😀",
        "empty",
        "caught",
    ]
    return  # noqa: PLR1711 - explicit repository returns
