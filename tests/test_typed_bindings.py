"""IR binding and iteration plans preserve mutations and snapshot iteration."""

from pathlib import Path

import pytest

from py2rust.compiler import memory, pipeline

from . import test_optimization as cases
from .test_typed_liveness import test_move_and_copy_execution as run_case

SOURCE = """def scan(values: list[int]) -> int:
    total: int = 0
    for item in values:
        total = total + item
    return total

def snapshot(values: list[int]) -> int:
    total: int = 0
    for item in values:
        values.clear()
        total = total + item
    return total

def items(rows: list[list[int]]) -> int:
    for row in rows:
        row.append(1)
    return len(rows)

def branches(flag: bool) -> int:
    total = 0
    if flag:
        local = 2
        total = total + local
    else:
        local = 3
        total = total + local
    return total

if __name__ == "__main__":
    total: int = 0
    for item in [1, 2]:
        total = total + item
    assert total == 3
"""


def forbidden(*args, **kwargs) -> None:
    raise AssertionError("typed binding or iteration policy fell back to AST analysis")


def disable_legacy(monkeypatch) -> None:
    monkeypatch.setattr(memory, "_legacy_iteration_use", forbidden)
    monkeypatch.setattr(memory, "_legacy_mutable_bindings", forbidden)
    return  # noqa: PLR1711


def test_prepared_bindings_and_iteration_equivalence(tmp_path: Path, monkeypatch) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    bindings = dict(prepared.readability.bindings)
    assert bindings["main.scan"] == {"total"}
    assert bindings["main.snapshot"] == {"total", "values"}
    item_function = next(
        function for module in prepared.modules for function in module.functions if function.name == "main.items"
    )
    row_binding = item_function.body[0].target
    assert bindings["main.items"] == {row_binding}
    assert bindings["main.branches"] == {"total"}
    loops = {item.target: plan for item, plan in prepared.memory.iterations}
    assert loops[row_binding].mode == "borrow" and not loops[row_binding].borrow_item
    assert any(plan.reason == "iteration_source_may_change" for _, plan in prepared.memory.iterations)
    current = pipeline.emit_rust(prepared)
    original_link = pipeline.linked_tree

    def legacy(*args, **kwargs):
        kwargs["iteration_facts"] = None
        kwargs["binding_plans"] = ()
        kwargs["entry_bindings"] = None
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
        cases.test_iteration_snapshot_and_item_ownership,
        cases.test_idiomatic_returns_and_mutation,
        cases.test_sequence_views_preserve_snapshots,
    ],
)
def test_native_binding_and_loop_execution(tmp_path: Path, monkeypatch, optimize: bool, case) -> None:
    disable_legacy(monkeypatch)
    run_case(tmp_path, monkeypatch, optimize, case)
    return  # noqa: PLR1711
