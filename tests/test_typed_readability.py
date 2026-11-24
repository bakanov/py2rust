"""Readable tail branches must preserve values, failures and cleanup ordering."""

from dataclasses import replace
from pathlib import Path

import pytest

from py2rust.compiler import pipeline, readability
from py2rust.compiler.service import ServiceCompiler

from .test_services import parity

SOURCE = """from py2rust.stdlib import json_loads, json_int

def classify(value: int) -> str:
    if value < 0:
        return "negative"
    elif value == 0:
        return "zero"
    else:
        answer: str = "positive"
        return answer

def parse(value: str) -> int:
    return json_int(json_loads(value))

def choose(value: str, enabled: bool) -> int:
    if enabled:
        return parse(value)
    else:
        return 7

def early(value: int) -> int:
    if value == 0:
        return 10
    print("later")
    return 20

def guarded(value: str) -> int:
    try:
        if value == "skip":
            return 8
        else:
            return parse(value)
    finally:
        print("cleanup")

def run() -> None:
    for value in [-1, 0, 1]:
        print(classify(value))
    print(choose("3", True))
    print(choose("invalid", False))
    try:
        choose("true", True)
    except Exception:
        print("caught")
    print(early(0))
    print(early(1))
    print(guarded("skip"))
    try:
        guarded("true")
    except Exception:
        print("cleanup before catch")

if __name__ == "__main__":
    run()
"""


def function(code: str, name: str) -> str:
    return code.split(f"fn py__main__{name}(", 1)[1].split("\nfn ", 1)[0]


def test_prepared_branch_plan_and_before_after(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    before = pipeline.emit_rust(replace(prepared, readability=readability.ReadabilityPlan(frozenset())))
    after = pipeline.emit_rust(prepared)
    assert 'return Ok("negative".to_string());' in function(before, "classify")
    assert 'Ok("negative".to_string())' in function(after, "classify")
    assert "return " not in function(after, "classify")
    assert "return py__main__parse(value);" in function(before, "choose")
    assert "return " not in function(after, "choose")
    assert "py__main__parse(value)" in function(after, "choose")
    assert "return Ok(10i64);" in function(after, "early")
    assert function(before, "guarded") == function(after, "guarded")

    def unexpected(*args, **kwargs) -> None:
        raise AssertionError("emission reran readability analysis")

    monkeypatch.setattr(readability, "analyze", unexpected)
    assert pipeline.emit_rust(prepared) == after
    return  # noqa: PLR1711


@pytest.mark.parametrize("idioms", [False, True])
def test_branch_values_errors_and_cleanup(tmp_path: Path, monkeypatch, idioms: bool) -> None:
    original = ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        original(self, *args, **kwargs)
        self.optimize_idioms = idioms
        return  # noqa: PLR1711

    monkeypatch.setattr(ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(
        ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    assert parity(tmp_path, SOURCE) == (
        "negative\nzero\npositive\n3\n7\ncaught\n10\nlater\n20\ncleanup\n8\ncleanup\ncleanup before catch\n"
    )
    return  # noqa: PLR1711
