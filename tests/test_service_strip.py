"""Python character-set trimming, Unicode whitespace, evaluation order and argument rejection."""

import json
import random
from pathlib import Path

import pytest
from py2rust.compiler.service import ServiceCompiler, ServiceError

from .test_services import parity, run


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_trimming_matches_python(tmp_path: Path, engine: str) -> None:
    whitespace = "".join(chr(i) for i in range(0x110000) if chr(i).isspace())
    pairs = [
        ("", ""),
        ("abba", "ab"),
        ("abcba", "ab"),
        ("  x  ", ""),
        ("\0x\0", "\0"),
        ("é😀e\u0301é", "é😀\u0301"),
        (whitespace + "x" + whitespace, whitespace),
        ("\u200bx\u200b", " "),
        ("a" * 65536 + "x" + "a" * 65536, "a" * 4096),
    ]
    rng = random.Random(97097)
    alphabet = list("abcé世界😀e\u0301\0\u200b") + list(whitespace)
    for _ in range(600):
        pairs.append(
            ("".join(rng.choices(alphabet, k=rng.randrange(50))), "".join(rng.choices(alphabet, k=rng.randrange(12))))
        )
    (tmp_path / "cases.json").write_text(json.dumps(pairs))
    source = """from py2rust.stdlib import Json, json_array, json_loads, json_string, json_dumps, read_text
def check() -> None:
    results: list[Json] = []
    for item in json_array(json_loads(read_text("cases.json"))):
        value: str = json_string(item[0])
        chars: str = json_string(item[1])
        results.append([value.strip(), value.lstrip(), value.rstrip(), value.strip(None), value.lstrip(None),
                        value.rstrip(None), value.strip(chars), value.lstrip(chars), value.rstrip(chars)])
    print(json_dumps(results))
    return
if __name__ == "__main__":
    check()
"""
    result = run(tmp_path, source, engine)
    assert result.returncode == 0, result.stderr
    expected = [
        [
            value.strip(),
            value.lstrip(),
            value.rstrip(),
            value.strip(None),
            value.lstrip(None),
            value.rstrip(None),
            value.strip(chars),
            value.lstrip(chars),
            value.rstrip(chars),
        ]
        for value, chars in pairs
    ]
    assert json.loads(result.stdout) == expected
    return  # noqa: PLR1711


def test_trimming_evaluates_once_and_recovers(tmp_path: Path) -> None:
    result = parity(
        tmp_path,
        """
def observed(label: str, value: str) -> str:
    print(label)
    return value
def nothing() -> None:
    print("none")
    return
def broken() -> str:
    print("broken")
    assert False, "bad operand"
    return ""
def check() -> None:
    print(observed("receiver", "ababxabba").strip(observed("chars", "ab")))
    print(observed("left", "  x  ").lstrip(nothing()))
    print(observed("right", "  x  ").rstrip(nothing()))
    try:
        text: str = broken().lstrip(observed("never", "x"))
    except Exception:
        print("receiver recovered")
    try:
        text: str = observed("before argument", "x").rstrip(broken())
    except Exception:
        print("argument recovered")
    print(" ".strip(""))
    print(" good ".lstrip().rstrip())
    return
if __name__ == "__main__":
    check()
""",
    )
    assert result == (
        "receiver\nchars\nx\nleft\nnone\nx  \nright\nnone\n  x\nbroken\nreceiver recovered\n"
        "before argument\nbroken\nargument recovered\n \ngood\n"
    )
    return  # noqa: PLR1711


@pytest.mark.parametrize("method", ["strip", "lstrip", "rstrip"])
@pytest.mark.parametrize("arguments", ["1", "True", "b'x'", "['x']", "'x', 'y'", "chars='x'"])
def test_invalid_trimming_arguments(method: str, arguments: str) -> None:
    with pytest.raises(ServiceError):
        ServiceCompiler().compile(f'def check() -> None:\n    text: str = "x".{method}({arguments})\n    return\n')
    return  # noqa: PLR1711
