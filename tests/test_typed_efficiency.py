"""Prepared text representations preserve Unicode, bounds and cache semantics."""

from pathlib import Path

import pytest

from py2rust.compiler import optimization, pipeline, service

from . import test_optimization as cases
from .test_codepoint_index import SOURCE as CODEPOINT
from .test_services import parity
from .test_unicode_views import SOURCE as UNICODE

SOURCE = CODEPOINT + """
def mixed(text: str) -> str:
    print(ord(text[0]))
    return text[1:]

def uncertain(text: str) -> int:
    return ord(text[int("0")]) + ord(text[1])

def changed(text: str) -> int:
    print(len(text))
    text = "new"
    return len(text)

def lengths(text: str) -> int:
    return len(text) + len(text)

def once(text: str) -> str:
    return text[0]
"""


def forbidden(*args, **kwargs) -> None:
    raise AssertionError("typed text efficiency fell back to AST analysis")


def disable_legacy(monkeypatch) -> None:
    monkeypatch.setattr(optimization, "_legacy_text_accesses", forbidden)
    monkeypatch.setattr(optimization, "_legacy_cached_lengths", forbidden)
    return  # noqa: PLR1711


def test_prepared_text_decisions_and_equivalence(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.efficiency.functions}
    assert plans["main.checksum"].indexes[0].representation == "CodepointIndex"
    assert plans["main.mixed"].indexes[0].representation == "TextIndex"
    assert plans["main.uncertain"].indexes[0].representation == "TextIndex"
    assert not plans["main.changed"].lengths
    assert len(plans["main.lengths"].lengths) == 1
    assert not plans["main.once"].indexes
    current = pipeline.emit_rust(prepared)
    original = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["efficiency_plans"] = None
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        assert pipeline.emit_rust(prepared) == current
    disable_legacy(monkeypatch)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("source", [CODEPOINT, UNICODE])
def test_native_unicode_execution(tmp_path: Path, monkeypatch, optimize: bool, source: str) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    disable_legacy(monkeypatch)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, value: pipeline.compile_typed({"main": (tmp_path / "main.py", value)}),
    )
    parity(tmp_path, source)
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
def test_native_cached_lengths(tmp_path: Path, monkeypatch, optimize: bool) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    disable_legacy(monkeypatch)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, value: pipeline.compile_typed({"main": (tmp_path / "main.py", value)}),
    )
    cases.test_cached_length_semantics(tmp_path, monkeypatch, optimize)
    return  # noqa: PLR1711


SHADOWED = """def ord(text: str) -> int:
    return 7

def len(text: str) -> int:
    return 14

def inspect(text: str) -> int:
    return ord(text[0]) + ord(text[1]) + len(text)

if __name__ == "__main__":
    assert inspect("é🙂") == 28
    print("resolved user functions")
"""


def test_shadowed_builtins(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SHADOWED)})
    plan = next(plan for plan in prepared.efficiency.functions if plan.function == "main.inspect")
    assert plan.indexes[0].representation == "TextIndex"
    assert not plan.lengths
    test_native_unicode_execution(tmp_path, monkeypatch, True, SHADOWED)
    return  # noqa: PLR1711
