"""IR view plans preserve snapshots, owned escapes and backing lifetimes."""

from pathlib import Path

import pytest

from py2rust.compiler import memory, optimization, pipeline

from . import test_optimization as cases
from .test_typed_move_safety import (
    test_native_moves_preserve_views_and_resources as run_case,
)

SOURCE = """from py2rust.stdlib import Json, json_array

def text(value: str) -> str:
    first: str = value[1:]
    second: str = first[:2]
    return second

def sequence(values: list[int]) -> list[int]:
    first: list[int] = values[1:]
    second: list[int] = first[:2]
    return second

def mutated(values: list[int]) -> list[int]:
    first: list[int] = values[1:]
    values.append(7)
    return first

def inferred(value: str) -> str:
    first = value[1:]
    return first

def arrays(document: Json) -> list[Json]:
    items: list[Json] = json_array(document)
    return items

if __name__ == "__main__":
    pass
"""


def forbidden_legacy(*args, **kwargs) -> None:
    raise AssertionError("typed view planning used an AST scanner")


def disable_legacy(monkeypatch) -> None:
    monkeypatch.setattr(optimization, "_legacy_string_slice_views", forbidden_legacy)
    monkeypatch.setattr(memory, "_legacy_sequence_slice_views", forbidden_legacy)
    monkeypatch.setattr(memory, "_legacy_json_array_views", forbidden_legacy)
    return  # noqa: PLR1711


def test_plans_and_generation_equivalence(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.views}
    assert plans["main.text"].bindings("text") == {"first": "value", "second": "value"}
    assert plans["main.sequence"].bindings("sequence") == {"first": "values", "second": "values"}
    assert plans["main.mutated"].views == ()
    assert plans["main.inferred"].bindings("text") == {"first": "value"}
    assert plans["main.arrays"].bindings("array") == {"items": "document"}
    current = pipeline.emit_rust(prepared)
    original_link = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["view_plans"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        assert pipeline.emit_rust(prepared) == current
    disable_legacy(monkeypatch)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize(
    "case",
    [
        cases.test_text_indexes_and_views,
        cases.test_json_views_and_owned_escapes,
        cases.test_sequence_views_preserve_snapshots,
        cases.test_sequence_views_bounds_and_owned_escape,
        cases.test_array_views_and_borrowed_serialization,
    ],
)
def test_native_view_execution(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    disable_legacy(monkeypatch)
    run_case(tmp_path, monkeypatch, optimize, case)
    return  # noqa: PLR1711
