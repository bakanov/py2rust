"""Only closed parsers with immutable input and Copy results may retain answers."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """from py2rust.stdlib import regex_fullmatch, env_get

def parse(text: str) -> tuple[int, int, int]:
    assert regex_fullmatch(r"[0-9]+\\.[0-9]+\\.[0-9]+", text), "version syntax"
    parts: list[str] = text.split(".")
    values: list[int] = []
    for part in parts:
        number: int = int(part)
        assert number <= 2147483647, "component range"
        values.append(number)
    return (values[0], values[1], values[2])

def noisy(text: str) -> int:
    print("observed")
    total: int = 0
    for char in text:
        total = total + int(char)
    return total

def external(text: str) -> int:
    total: int = 0
    for char in text:
        total = total + int(char)
    return total + len(env_get("PY2RUST_TEST_MISSING_MEMO", ""))

def rebound(text: str) -> int:
    text = text + "0"
    total: int = 0
    for char in text:
        total = total + int(char)
    return total

def owned(text: str) -> list[int]:
    result: list[int] = []
    for char in text:
        result.append(int(char))
    return result

def check() -> None:
    for index in range(70):
        assert parse(str(index) + ".2.3") == (index, 2, 3)
    for index in range(3):
        assert parse("0.2.3") == (0, 2, 3)
        assert noisy("12") == 3
        assert external("") >= 0
        assert rebound("12") == 3
        result: list[int] = owned("12")
        result[0] = 99
        assert owned("12")[0] == 1
        try:
            parse("2147483648.2.3")
        except Exception as error:
            print(str(error))
    print("memoization passed")
    return

if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_parser_cache(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    original = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original(self, *args, **kwargs)
        return

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    if frontend == "typed":
        monkeypatch.setattr(
            service.ServiceCompiler,
            "compile",
            lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
        )
    generated = service.ServiceCompiler().compile(SOURCE)
    assert generated.count("rt::MemoCache<") == int(optimize)
    output = parity(tmp_path, SOURCE)
    assert output.count("observed") == 3
    assert output.count("component range") == 3
    assert output.endswith("memoization passed\n")
    return
