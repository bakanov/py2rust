"""The incoming value dies when an assignment installs a replacement value."""

from pathlib import Path

import pytest

from py2rust.compiler import pipeline, service
from .test_services import parity

SOURCE = """def append(values: list[int], number: int) -> list[int]:
    assert number >= 0, "negative"
    values.append(number)
    return values

def replace() -> list[int]:
    values: list[int] = []
    for i in range(4):
        values = append(values, i)
    return values

def repeated() -> list[int]:
    values: list[int] = [1]
    values = append(values, len(values))
    return values

def protected() -> list[int]:
    values: list[int] = [7]
    try:
        values = append(values, -1)
    except Exception:
        assert values == [7]
    return values

def check() -> None:
    assert replace() == [0, 1, 2, 3]
    assert repeated() == [1, 1]
    assert protected() == [7]
    print("replacement ownership")
    return
if __name__ == "__main__":
    check()
"""


@pytest.mark.parametrize("frontend", ["typed", "legacy"])
@pytest.mark.parametrize("optimize", [False, True])
def test_self_replacing_assignment(tmp_path: Path, monkeypatch, frontend: str, optimize: bool) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.liveness}
    for name, expected in [("replace", "move"), ("repeated", "copy"), ("protected", "copy")]:
        uses = [use for use in plans[f"main.{name}"].uses if use.expression.value == "values"]
        first_line = min(use.expression.source.line for use in uses)
        assert all(use.mode == expected for use in uses if use.expression.source.line == first_line)
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
    assert parity(tmp_path, SOURCE) == "replacement ownership\n"
    return
