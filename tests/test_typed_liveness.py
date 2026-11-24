"""IR liveness preserves branch, loop, cleanup and snapshot ownership behavior."""

from pathlib import Path

import pytest

from py2rust.compiler import memory, pipeline, service

from . import test_optimization as cases

SOURCE = """def choose(flag: bool) -> str:
    value: str = "ready"
    if flag:
        return value
    saved: str = value
    print(saved)
    return value

def walk(count: int) -> str:
    value: str = "kept"
    for index in range(count):
        if index == 1:
            continue
        if index == 3:
            break
        print(value)
    try:
        print(value)
    finally:
        print(value)
    return value

if __name__ == "__main__":
    print(choose(True))
    print(walk(4))
"""


def forbidden_ast_liveness(*args, **kwargs) -> None:
    raise AssertionError("typed liveness fell back to AST analysis")


def test_prepared_liveness_matches_previous_decisions(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    plans = {plan.function: plan for plan in prepared.memory.liveness}
    uses = sorted(
        [use for use in plans["main.walk"].uses if use.expression.value == "value"],
        key=lambda use: use.expression.source.line,
    )
    assert [use.mode for use in uses] == ["copy", "copy", "copy", "move"]
    assert [use.reason for use in uses] == [
        "value_live_after_use",
        "protected_control_flow",
        "protected_control_flow",
        "last_use_on_all_successors",
    ]
    current = pipeline.emit_rust(prepared)
    original_link = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["liveness"] = None
        return original_link(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "linked_tree", legacy)
        assert pipeline.emit_rust(prepared) == current
    monkeypatch.setattr(memory, "_legacy_last_uses", forbidden_ast_liveness)
    assert pipeline.emit_rust(prepared) == current
    return  # noqa: PLR1711


@pytest.mark.parametrize("optimize", [False, True])
@pytest.mark.parametrize("case", [cases.test_last_use_control_flow, cases.test_iteration_snapshot_and_item_ownership])
def test_move_and_copy_execution(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    original_init = service.ServiceCompiler.__init__

    def initialize(self, *args, **kwargs) -> None:
        kwargs["optimize"] = optimize
        original_init(self, *args, **kwargs)
        return  # noqa: PLR1711

    monkeypatch.setattr(service.ServiceCompiler, "__init__", initialize)
    monkeypatch.setattr(memory, "_legacy_last_uses", forbidden_ast_liveness)
    monkeypatch.setattr(
        service.ServiceCompiler,
        "compile",
        lambda self, source: pipeline.compile_typed({"main": (tmp_path / "main.py", source)}),
    )
    case(tmp_path, monkeypatch, optimize)
    return  # noqa: PLR1711
