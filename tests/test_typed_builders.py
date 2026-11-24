"""Prepared builders preserve evaluation order, failure snapshots and ownership."""

from pathlib import Path

import pytest

from py2rust.compiler import optimization, pipeline, service

from .test_optimization import SOURCE
from .test_services import parity

MAIN = """if __name__ == "__main__":
    value: str = "start"
    before: str = value
    value = value + "[" + value + "]"
    assert before == "start" and value == "start[start]"
    value = "prefix" + value
    assert value == "prefixstart[start]"
    number: int = 1
    number = number + 2
    assert number == 3
    print(value)
"""


def forbidden(*args, **kwargs) -> None:
    raise AssertionError("typed builder fell back to AST recognition")


@pytest.mark.parametrize("source", [SOURCE, MAIN])
def test_prepared_builder_equivalence(tmp_path: Path, monkeypatch, source: str) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", source)})
    decisions = [plan for _, plan in prepared.efficiency.appends if plan is not None]
    assert decisions and any(plan.suffix_count > 1 for plan in decisions)
    current = pipeline.emit_rust(prepared)
    original = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["append_facts"] = None
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        assert pipeline.emit_rust(prepared) == current
    monkeypatch.setattr(optimization, "_legacy_string_append", forbidden)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("source", [SOURCE, MAIN])
def test_native_builder_execution(tmp_path: Path, monkeypatch, optimize: bool, source: str) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(optimization, "_legacy_string_append", forbidden)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, value: pipeline.compile_typed({"main": (tmp_path / "main.py", value)}),
    )
    parity(tmp_path, source)
    return  # noqa: PLR1711
