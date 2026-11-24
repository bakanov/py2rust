"""Ownership explanations preserve materialization, resource and backing priorities."""

from dataclasses import replace
from pathlib import Path

from py2rust.compiler import pipeline
from py2rust.compiler.move_safety import MoveContext, can_transfer, owned_boundary

from .test_committed_costs import SOURCE


def test_ownership_explanation_priorities() -> None:
    owned = MoveContext(local=True, last_use=True, borrowed=False, is_view=False, backs_view=False, type_safe=True)
    assert can_transfer(owned)
    assert owned_boundary(owned, "str").mode == "move"
    borrowed_resource = replace(owned, borrowed=True, type_safe=False)
    assert owned_boundary(borrowed_resource, "Record").mode == "materialize"
    assert not can_transfer(borrowed_resource)
    resource_backing = replace(owned, type_safe=False, backs_view=True)
    assert owned_boundary(resource_backing, "Record").reason == "preserve_resource_lifetime_or_unreviewed_type"
    indexed_owner = replace(owned, backs_view=True)
    assert owned_boundary(indexed_owner, "str").reason == "retain_view_backing_storage"
    assert not can_transfer(indexed_owner)
    assert owned_boundary(replace(owned, is_view=True), "str").mode == "materialize"
    assert (
        owned_boundary(replace(owned, last_use=False), "str", "protected_control_flow").reason
        == "protected_control_flow"
    )
    assert owned_boundary(replace(owned, last_use=False), "str").reason == "ownership_transfer_not_proven"
    assert owned_boundary(owned, "int") is None
    return  # noqa: PLR1711


def test_typed_committed_ownership_explanations(tmp_path: Path) -> None:
    prepared = pipeline.prepare_typed({"main": (tmp_path / "main.py", SOURCE)})
    explained = pipeline.emit_program(prepared, explain=True)
    assert explained.code == pipeline.emit_rust(prepared)
    decisions = {
        (row["symbol"], decision["mode"], decision["reason"])
        for row in explained.optimization_report["functions"]
        for decision in row["decisions"]
        if decision["operation"] == "owned_boundary"
    }
    assert decisions == {
        ("py__main__moving", "move", "last_use_on_all_successors"),
        ("py__main__copying", "copy", "value_live_after_use"),
        ("py__main__materializing", "materialize", "borrowed_value_requires_owned_result"),
        ("py__main__cleanup", "copy", "protected_control_flow"),
    }
    return  # noqa: PLR1711
